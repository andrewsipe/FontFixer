"""
Family slant review — interactive post-pass.

After the main handlers finish, compare measured italic angles within each
family and advise when italic/oblique *flags* look wrong relative to siblings.
Angles are never rewritten here.

Skipped (no recommendation) when the family is incomplete or ambiguous —
e.g. no upright cluster, all upright, single member, or no clear angle spread.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None  # type: ignore[misc, assignment]

from .bitfield import FS_SELECTION, MAC_STYLE
from .data_models import HANDLER_STYLE
from .style_analyzer import FontStyleAnalyzer

try:
    import FontCore.core_console_styles as cs
    from FontCore.core_console_styles import QuitRequested

    console = cs.get_console()
except ImportError:
    cs = None  # type: ignore[assignment]
    console = None

    class QuitRequested(Exception):  # type: ignore[no-redef]
        pass

# Match the style analyzer floor for “measurably slanted.”
MIN_SLANT_DEG = 2.0
# Family needs at least this |angle| spread between upright and slanted peaks.
MIN_FAMILY_SPREAD_DEG = 2.0

_STYLE_NAME_IDS = (2, 17, 4)
_FAMILY_NAME_IDS = (16, 1)
_ITALIC_RE = re.compile(r"\bitalic\b", re.I)
_OBLIQUE_RE = re.compile(r"\boblique\b", re.I)
_STYLE_TOKEN_RE = re.compile(
    r"(?i)[-_]?(?:"
    r"thin|extralight|ultralight|light|book|regular|roman|medium|"
    r"semibold|demibold|bold|extrabold|ultrabold|black|heavy|"
    r"italic|oblique|condensed|compressed|narrow|extended|expanded|wide"
    r")$"
)


class ClusterKind(str, Enum):
    UPRIGHT = "upright"
    FORWARD = "forward"  # negative angle (typical LTR italic)
    BACKWARD = "backward"  # positive angle


@dataclass
class FamilyMember:
    path: Path
    family_key: str
    style_label: str
    measured_angle: float
    name_italic: bool
    name_oblique: bool
    fs_italic: bool
    fs_oblique: bool
    mac_italic: bool
    cluster: Optional[ClusterKind] = None
    want_italic: bool = False
    want_oblique: bool = False

    @property
    def flag_italic_or_oblique(self) -> bool:
        return self.fs_italic or self.fs_oblique or self.mac_italic

    @property
    def want_slanted(self) -> bool:
        return self.want_italic or self.want_oblique


@dataclass
class FamilyFlagFix:
    path: Path
    style_label: str
    measured_angle: float
    set_italic: bool
    set_oblique: bool
    clear_slant_flags: bool
    note: str


@dataclass
class FamilyRecommendation:
    family_key: str
    members: List[FamilyMember]
    fixes: List[FamilyFlagFix]
    summary: str
    skipped_reason: Optional[str] = None

    @property
    def actionable(self) -> bool:
        return self.skipped_reason is None and bool(self.fixes)


@dataclass
class FamilyReviewReport:
    families_seen: int = 0
    skipped: List[FamilyRecommendation] = field(default_factory=list)
    ok: List[FamilyRecommendation] = field(default_factory=list)
    recommended: List[FamilyRecommendation] = field(default_factory=list)


def _name_record_text(font: TTFont, name_ids: Sequence[int]) -> Optional[str]:
    """Return the first non-empty name string, respecting *name_ids* priority.

    Walks IDs in order (e.g. typographic 16 before legacy 1) so RIBBI-split
    families like ``Babel Black`` / ``Babel Book`` still group under ``Babel``.
    Within each ID, prefer Windows English, then any platform/lang.
    """
    if "name" not in font:
        return None
    for name_id in name_ids:
        preferred = None
        fallback = None
        for record in font["name"].names:
            if record.nameID != name_id:
                continue
            try:
                text = record.toUnicode().strip()
            except Exception:
                continue
            if not text:
                continue
            if record.platformID == 3 and record.langID == 0x409:
                preferred = text
                break
            if fallback is None:
                fallback = text
        if preferred or fallback:
            return preferred or fallback
    return None


def _filename_family_key(path: Path) -> str:
    stem = path.stem
    # Drop common NV_ / vendor prefixes lightly; keep rest for grouping.
    key = stem
    # Peel trailing style tokens repeatedly.
    changed = True
    while changed:
        changed = False
        new_key = _STYLE_TOKEN_RE.sub("", key)
        if new_key != key and new_key:
            key = new_key.rstrip("-_")
            changed = True
    return key or stem


def family_key_for_font(font: TTFont, path: Path) -> str:
    named = _name_record_text(font, _FAMILY_NAME_IDS)
    if named:
        return named
    return _filename_family_key(path)


def style_label_for_font(font: TTFont, path: Path) -> str:
    named = _name_record_text(font, _STYLE_NAME_IDS)
    if named:
        return named
    return path.stem


def _name_blob(font: TTFont) -> str:
    if "name" not in font:
        return ""
    parts = []
    for record in font["name"].names:
        if record.nameID in (1, 2, 4, 6, 16, 17):
            try:
                parts.append(record.toUnicode())
            except Exception:
                continue
    return " ".join(parts)


def _name_has_italic(font: TTFont) -> bool:
    return bool(_ITALIC_RE.search(_name_blob(font)))


def _name_has_oblique(font: TTFont) -> bool:
    return bool(_OBLIQUE_RE.search(_name_blob(font)))


def load_family_member(path: Path) -> Optional[FamilyMember]:
    """Open a font and build a FamilyMember snapshot."""
    try:
        font = TTFont(path, lazy=True)
    except Exception:
        return None

    try:
        analyzer = FontStyleAnalyzer(font)
        angle = float(analyzer.italic_angle)
        os2 = font["OS/2"] if "OS/2" in font else None
        head = font["head"] if "head" in font else None
        fs = int(getattr(os2, "fsSelection", 0) or 0) if os2 is not None else 0
        mac = int(getattr(head, "macStyle", 0) or 0) if head is not None else 0
        fs_oblique = False
        if os2 is not None and getattr(os2, "version", 0) >= 4:
            fs_oblique = FS_SELECTION.flags["OBLIQUE"].is_set(fs)

        return FamilyMember(
            path=Path(path),
            family_key=family_key_for_font(font, Path(path)),
            style_label=style_label_for_font(font, Path(path)),
            measured_angle=angle,
            name_italic=_name_has_italic(font),
            name_oblique=_name_has_oblique(font),
            fs_italic=FS_SELECTION.flags["ITALIC"].is_set(fs),
            fs_oblique=fs_oblique,
            mac_italic=MAC_STYLE.flags["ITALIC"].is_set(mac),
        )
    except Exception:
        return None
    finally:
        try:
            font.close()
        except Exception:
            pass


def _is_relatively_upright(member: FamilyMember, members: Sequence[FamilyMember]) -> bool:
    """True when this cut is the vertical side of the family (flags should stay roman)."""
    if member.name_italic or member.name_oblique:
        return False

    abs_ang = abs(member.measured_angle)
    if abs_ang < MIN_SLANT_DEG:
        return True

    # Steeper siblings (by |angle|).
    steeper = [
        abs(o.measured_angle)
        for o in members
        if o is not member
        and abs(o.measured_angle) >= abs_ang + MIN_FAMILY_SPREAD_DEG
    ]
    if not steeper:
        return False

    # Only treat as "roman noise" when the family actually has a clear slant side
    # (named italic/oblique, or a sibling past a real-italic-ish floor).
    has_named_slant = any(
        (o.name_italic or o.name_oblique) for o in members if o is not member
    )
    real_steeper = [s for s in steeper if s >= 8.0]
    if not has_named_slant and not real_steeper:
        return False

    ref = max(real_steeper or steeper)
    return abs_ang < ref * 0.5


def assign_clusters(members: List[FamilyMember]) -> None:
    """
    Tag each member upright vs slanted.

    When the family already has Italic/Oblique *names*, unlabeled cuts are
    treated as upright for flag purposes (measured angle noise on Romans must
    not invent a third slant band). Without named slants, fall back to angle.
    """
    family_has_named_slant = any(m.name_italic or m.name_oblique for m in members)

    for member in members:
        if member.name_italic or member.name_oblique:
            if member.measured_angle >= MIN_SLANT_DEG:
                member.cluster = ClusterKind.BACKWARD
            else:
                # Named italic/oblique, or near-zero / negative → forward bucket
                member.cluster = ClusterKind.FORWARD
            continue

        if family_has_named_slant:
            # Regular/Bold/etc. beside named italics → upright side of the family
            member.cluster = ClusterKind.UPRIGHT
            continue

        if _is_relatively_upright(member, members):
            member.cluster = ClusterKind.UPRIGHT
        elif member.measured_angle <= -MIN_SLANT_DEG:
            member.cluster = ClusterKind.FORWARD
        elif member.measured_angle >= MIN_SLANT_DEG:
            member.cluster = ClusterKind.BACKWARD
        else:
            member.cluster = ClusterKind.UPRIGHT


def _cluster_groups(
    members: Sequence[FamilyMember],
) -> Dict[ClusterKind, List[FamilyMember]]:
    groups: Dict[ClusterKind, List[FamilyMember]] = defaultdict(list)
    for member in members:
        if member.cluster is not None:
            groups[member.cluster].append(member)
    return groups


def _desired_flags(member: FamilyMember) -> Tuple[bool, bool]:
    """Return (want_italic, want_oblique) for a clustered member."""
    if member.cluster == ClusterKind.UPRIGHT:
        return False, False
    # Slanted: prefer oblique label when present, else italic.
    if member.name_oblique:
        return False, True
    return True, False


def analyze_family(members: List[FamilyMember]) -> FamilyRecommendation:
    """
    Decide skip / ok / recommend for one family.

    Actionable only when there is a clear upright cluster and at least one
    slanted cluster, and current flags disagree with that picture.
    """
    if not members:
        return FamilyRecommendation(
            family_key="?",
            members=[],
            fixes=[],
            summary="empty",
            skipped_reason="empty family",
        )

    family_key = members[0].family_key
    assign_clusters(members)
    groups = _cluster_groups(members)

    upright = groups.get(ClusterKind.UPRIGHT, [])
    forward = groups.get(ClusterKind.FORWARD, [])
    backward = groups.get(ClusterKind.BACKWARD, [])
    slanted = forward + backward
    named_split = any(m.name_italic or m.name_oblique for m in members)

    if len(members) < 2:
        return FamilyRecommendation(
            family_key=family_key,
            members=members,
            fixes=[],
            summary="single cut in this run",
            skipped_reason="incomplete family (only one cut in this run)",
        )

    if not upright:
        return FamilyRecommendation(
            family_key=family_key,
            members=members,
            fixes=[],
            summary="no upright side",
            skipped_reason="incomplete or all-slanted family — no upright reference",
        )

    if not slanted:
        return FamilyRecommendation(
            family_key=family_key,
            members=members,
            fixes=[],
            summary="no slanted side",
            skipped_reason="no slanted cuts to compare against",
        )

    # Angle-spread gate only when names don’t already define italic vs roman.
    if not named_split:
        upright_peak = sum(abs(m.measured_angle) for m in upright) / len(upright)
        slant_peak = sum(abs(m.measured_angle) for m in slanted) / len(slanted)
        if slant_peak - upright_peak < MIN_FAMILY_SPREAD_DEG:
            return FamilyRecommendation(
                family_key=family_key,
                members=members,
                fixes=[],
                summary="angle spread too small",
                skipped_reason=(
                    f"ambiguous spread ({slant_peak - upright_peak:.2f}° "
                    f"< {MIN_FAMILY_SPREAD_DEG}°)"
                ),
            )

    # Assign desired flags from clusters.
    for member in members:
        member.want_italic, member.want_oblique = _desired_flags(member)

    fixes: List[FamilyFlagFix] = []
    for member in members:
        need_italic = member.want_italic
        need_oblique = member.want_oblique
        need_clear = not need_italic and not need_oblique

        # Without a named Italic/Oblique cut, never invent SET from angle alone —
        # weight-correlated roman noise (common in this corpus) looks like a
        # "slanted" side. Still CLEAR flags that sit on the upright cluster.
        if not named_split and (need_italic or need_oblique):
            continue

        mismatch = (
            member.fs_italic != need_italic
            or member.fs_oblique != need_oblique
            or member.mac_italic != (need_italic or need_oblique)
        )
        if not mismatch:
            continue

        if need_clear:
            note = "clear italic flags (roman/upright in this family)"
        elif need_oblique:
            note = "set oblique flags"
        else:
            note = "set italic flags (slanted cut missing italic bits)"

        fixes.append(
            FamilyFlagFix(
                path=member.path,
                style_label=member.style_label,
                measured_angle=member.measured_angle,
                set_italic=need_italic,
                set_oblique=need_oblique,
                clear_slant_flags=need_clear,
                note=note,
            )
        )

    if not fixes:
        # Angle-only "slant" with no named italics → no actionable flag advice.
        if not named_split and slanted:
            return FamilyRecommendation(
                family_key=family_key,
                members=members,
                fixes=[],
                summary="roman-only family",
                skipped_reason=(
                    "roman-only family — no named italic/oblique cuts "
                    "(angle spread ignored for SET)"
                ),
            )
        return FamilyRecommendation(
            family_key=family_key,
            members=members,
            fixes=[],
            summary="flags match",
            skipped_reason=None,
        )

    clear_n = sum(1 for f in fixes if f.clear_slant_flags)
    set_n = len(fixes) - clear_n
    parts = []
    if clear_n:
        parts.append(f"clear italic on {clear_n}")
    if set_n:
        parts.append(f"set italic on {set_n}")
    return FamilyRecommendation(
        family_key=family_key,
        members=members,
        fixes=fixes,
        summary="; ".join(parts),
        skipped_reason=None,
    )


def build_review_report(paths: Iterable[Path]) -> FamilyReviewReport:
    """Load fonts, group by family, classify recommendations."""
    by_family: Dict[str, List[FamilyMember]] = defaultdict(list)
    for path in paths:
        member = load_family_member(Path(path))
        if member is None:
            continue
        by_family[member.family_key].append(member)

    report = FamilyReviewReport(families_seen=len(by_family))
    for family_key in sorted(by_family.keys(), key=str.lower):
        rec = analyze_family(by_family[family_key])
        if rec.skipped_reason:
            report.skipped.append(rec)
        elif rec.fixes:
            report.recommended.append(rec)
        else:
            report.ok.append(rec)
    return report


def apply_family_flag_fix(fix: FamilyFlagFix) -> bool:
    """Apply italic/oblique bit changes for one file. Returns True if saved."""
    font = TTFont(fix.path)
    changed = False
    try:
        if "OS/2" not in font or "head" not in font:
            return False

        os2 = font["OS/2"]
        head = font["head"]
        old_fs = os2.fsSelection
        old_mac = head.macStyle

        fs = old_fs
        fs = FS_SELECTION.flags["ITALIC"].clear(fs)
        fs = FS_SELECTION.flags["REGULAR"].clear(fs)
        if getattr(os2, "version", 0) >= 4:
            fs = FS_SELECTION.flags["OBLIQUE"].clear(fs)

        if fix.set_italic:
            fs = FS_SELECTION.flags["ITALIC"].set(fs)
        if fix.set_oblique and getattr(os2, "version", 0) >= 4:
            fs = FS_SELECTION.flags["OBLIQUE"].set(fs)
        if fix.clear_slant_flags or (not fix.set_italic and not fix.set_oblique):
            # Regular bit when not bold and not slanted.
            is_bold = FS_SELECTION.flags["BOLD"].is_set(old_fs)
            if not is_bold:
                fs = FS_SELECTION.flags["REGULAR"].set(fs)

        mac = MAC_STYLE.flags["ITALIC"].clear(old_mac)
        if fix.set_italic or fix.set_oblique:
            mac = MAC_STYLE.flags["ITALIC"].set(mac)

        if fs != old_fs:
            os2.fsSelection = fs
            changed = True
        if mac != old_mac:
            head.macStyle = mac
            changed = True

        if changed:
            font.save(fix.path)
        return changed
    finally:
        font.close()


def _emit(message: str = "") -> None:
    if cs is not None:
        cs.emit(message, console=console)
    else:
        print(message)


def _info(message: str) -> None:
    if cs is not None:
        cs.StatusIndicator("info").add_message(message).emit(console)
    else:
        print(f"[INFO] {message}")


def _success(message: str) -> None:
    if cs is not None:
        cs.StatusIndicator("success").add_message(message).emit(console)
    else:
        print(f"[OK] {message}")


def _warning(message: str) -> None:
    if cs is not None:
        cs.StatusIndicator("warning").add_message(message).emit(console)
    else:
        print(f"[WARN] {message}")


def _flag_summary(member: FamilyMember) -> str:
    flags = []
    if member.fs_italic:
        flags.append("ITALIC")
    if member.fs_oblique:
        flags.append("OBLIQUE")
    if member.mac_italic and not member.fs_italic:
        flags.append("macItalic")
    return "+".join(flags) if flags else "—"


def _side_label(member: FamilyMember) -> str:
    if member.cluster == ClusterKind.UPRIGHT:
        return "upright"
    return "slanted"


def _format_member_line(member: FamilyMember, *, mark: str = "·") -> str:
    indent = cs.indent(1) if cs is not None else "            "
    return (
        f"{indent}{mark} {member.path.name}  ·  {member.style_label}  ·  "
        f"{member.measured_angle:.2f}°  ·  {_side_label(member)}  ·  "
        f"{_flag_summary(member)}"
    )


def _format_fix_line(fix: FamilyFlagFix) -> str:
    indent = cs.indent(1) if cs is not None else "            "
    arrow = getattr(cs, "ARROW", "→") if cs is not None else "→"
    action = (
        "CLEAR italic"
        if fix.clear_slant_flags
        else ("SET oblique" if fix.set_oblique else "SET italic")
    )
    return (
        f"{indent}{arrow} {fix.path.name}  ({fix.style_label})  "
        f"{action}  ·  measured {fix.measured_angle:.2f}°"
    )


def _emit_survey_row(rec: FamilyRecommendation, *, name_width: int) -> None:
    """One StatusIndicator row aligned with the rest of FontFixer output."""
    detail = rec.skipped_reason or rec.summary
    name = f"{rec.family_key:<{name_width}}"
    em = getattr(cs, "EM_DASH", "—") if cs is not None else "—"
    line = f"{name}  {em}  {detail}"

    if cs is None:
        tag = (
            "WARNING"
            if rec.actionable
            else ("SKIPPED" if rec.skipped_reason else "OK")
        )
        print(f"{tag:<11} {line}")
        return

    if rec.actionable:
        cs.StatusIndicator("warning").add_message(line).emit(console)
    elif rec.skipped_reason:
        cs.StatusIndicator("skipped").add_message(line).emit(console)
    else:
        cs.StatusIndicator("ok").add_message(line).emit(console)


def print_diagnostic(report: FamilyReviewReport) -> None:
    """Scannable family outline using FontCore status labels."""
    all_recs = report.ok + report.skipped + report.recommended
    name_width = max((len(r.family_key) for r in all_recs), default=8)

    count = cs.fmt_count if cs is not None else (lambda n: str(n))
    _emit("")
    _info(
        f"Family slant review — {count(report.families_seen)} families · "
        f"{count(len(report.recommended))} to review · "
        f"{count(len(report.ok))} ok · "
        f"{count(len(report.skipped))} skipped"
    )

    _emit("")
    _info("Survey")
    for rec in sorted(all_recs, key=lambda r: r.family_key.lower()):
        _emit_survey_row(rec, name_width=name_width)

    if not report.recommended:
        return

    _emit("")
    _warning(
        f"{count(len(report.recommended))} families — "
        "style-pass flags look wrong vs the family’s upright/slanted split:"
    )
    for rec in report.recommended:
        _emit("")
        _emit_survey_row(rec, name_width=name_width)
        fix_paths = {f.path for f in rec.fixes}
        for member in sorted(rec.members, key=lambda m: m.path.name.lower()):
            mark = "*" if member.path in fix_paths else "·"
            _emit(_format_member_line(member, mark=mark))
        for fix in rec.fixes:
            _emit(_format_fix_line(fix))


def _prompt_mode() -> str:
    """Return 'all', 'review', or 'quit'."""
    if cs is not None and hasattr(cs, "prompt_select"):
        choice = cs.prompt_select(
            "Family slant recommendations — choose an action:",
            [
                "Apply all recommended flag fixes",
                "Review each recommended family",
                "Quit (leave flags unchanged)",
            ],
            default="Quit (leave flags unchanged)",
        )
        if choice.startswith("Apply all"):
            return "all"
        if choice.startswith("Review each"):
            return "review"
        return "quit"

    _emit("1) Apply all  2) Review each  3) Quit")
    raw = input("> ").strip().lower()
    if raw in ("1", "a", "all"):
        return "all"
    if raw in ("2", "r", "review"):
        return "review"
    return "quit"


def _prompt_apply_family(rec: FamilyRecommendation) -> bool:
    msg = (
        f"Apply flag fixes for family {rec.family_key!r} "
        f"({len(rec.fixes)} file(s))?"
    )
    if cs is not None and hasattr(cs, "prompt_confirm"):
        return cs.prompt_confirm(
            msg, action_prompt="Apply?", default=False, allow_quit=True
        )
    raw = input(f"{msg} [y/N/q]: ").strip().lower()
    if raw in ("q", "quit"):
        raise QuitRequested("quit")
    return raw in ("y", "yes")


def _apply_recommendation(rec: FamilyRecommendation) -> Tuple[int, int]:
    applied = 0
    failed = 0
    for fix in rec.fixes:
        try:
            if apply_family_flag_fix(fix):
                applied += 1
                _success(f"Updated flags: {fix.path.name}")
            else:
                _info(f"No flag change needed on disk: {fix.path.name}")
        except Exception as exc:
            failed += 1
            _warning(f"Failed {fix.path.name}: {exc}")
    return applied, failed


def run_family_slant_review(
    font_paths: Sequence[Path],
    *,
    interactive: bool = True,
) -> FamilyReviewReport:
    """
    Build diagnostic, print it, and optionally prompt to apply flag fixes.

    Non-interactive or empty recommendations → diagnostic only (or quiet ok).
    """
    report = build_review_report(font_paths)
    if report.families_seen == 0:
        return report

    print_diagnostic(report)

    if not report.recommended:
        _emit("")
        _info("No family flag recommendations.")
        return report

    if not interactive or not sys.stdin.isatty():
        _emit("")
        _info(
            "Skipping family flag prompts (non-interactive). "
            "Re-run in a terminal to Apply all / Review each."
        )
        return report

    try:
        mode = _prompt_mode()
    except Exception:
        return report

    if mode == "quit":
        _info("Family slant review: quit — no flag changes.")
        return report

    total_applied = 0
    total_failed = 0

    try:
        if mode == "all":
            for rec in report.recommended:
                a, f = _apply_recommendation(rec)
                total_applied += a
                total_failed += f
        else:
            for rec in report.recommended:
                _emit("")
                _info(f"Review: {rec.family_key} — {rec.summary}")
                for fix in rec.fixes:
                    _emit(_format_fix_line(fix))
                try:
                    if _prompt_apply_family(rec):
                        a, f = _apply_recommendation(rec)
                        total_applied += a
                        total_failed += f
                    else:
                        _info(f"Skipped family {rec.family_key}")
                except QuitRequested:
                    _info("Family slant review: quit.")
                    break
    except KeyboardInterrupt:
        _warning("Family slant review interrupted.")

    _emit("")
    _info(
        f"Family slant review finished — flags updated: {total_applied}, "
        f"failed: {total_failed}"
    )
    return report


def style_handler_enabled(enabled_handlers: Optional[List[str]]) -> bool:
    """True when the style handler ran (or all handlers)."""
    if enabled_handlers is None:
        return True
    return HANDLER_STYLE.full_name in enabled_handlers


def successful_font_paths(results: Sequence[dict]) -> List[Path]:
    """Paths to write targets from a processing run (prefer output_path)."""
    paths: List[Path] = []
    for result in results:
        if not result.get("success"):
            continue
        out = result.get("output_path") or result.get("file")
        if out:
            paths.append(Path(out))
    return paths
