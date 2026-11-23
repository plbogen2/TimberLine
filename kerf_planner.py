"""Kerf-aware 1D (linear lumber) and 2D (sheet stock) cut-list packing."""

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class LinearCut:
    label: str
    length_in: float


@dataclass
class PackedBoard:
    stock_length_in: float
    cuts: List[LinearCut]
    used_in: float
    kerf_loss_in: float
    offcut_in: float


def pack_linear_cuts(
    cuts: List[LinearCut],
    stock_length_in: float,
    kerf_in: float = 0.125,
    trim_in: float = 0.0,
) -> Tuple[List[PackedBoard], List[LinearCut]]:
    """Pack 1D cuts into stock boards using First-Fit Decreasing with kerf.

    Each cut after the first on a board consumes ``kerf_in`` before it.
    Returns ``(packed_boards, oversized_cuts)``.
    """
    usable_len = stock_length_in - trim_in
    oversized = [c for c in cuts if c.length_in > usable_len + 1e-6]
    valid = sorted(
        [c for c in cuts if c.length_in <= usable_len + 1e-6],
        key=lambda c: c.length_in,
        reverse=True,
    )

    boards: List[PackedBoard] = []
    for cut in valid:
        placed = False
        for board in boards:
            needed = cut.length_in + (kerf_in if board.cuts else 0.0)
            if board.used_in + needed <= usable_len + 1e-6:
                if board.cuts:
                    board.kerf_loss_in += kerf_in
                board.cuts.append(cut)
                board.used_in += needed
                board.offcut_in = usable_len - board.used_in
                placed = True
                break
        if not placed:
            boards.append(
                PackedBoard(
                    stock_length_in=stock_length_in,
                    cuts=[cut],
                    used_in=cut.length_in,
                    kerf_loss_in=0.0,
                    offcut_in=usable_len - cut.length_in,
                )
            )
    return boards, oversized


@dataclass
class SheetCut:
    label: str
    width_in: float
    length_in: float


@dataclass
class PackedSheet:
    sheet_width_in: float
    sheet_length_in: float
    cuts: List[SheetCut]
    used_area_sq_in: float
    waste_pct: float


def pack_sheet_cuts(
    cuts: List[SheetCut],
    sheet_width_in: float,
    sheet_length_in: float,
    kerf_in: float = 0.125,
) -> Tuple[List[PackedSheet], List[SheetCut]]:
    """Pack 2D rectangular parts onto sheets using shelf packing with kerf."""
    oversized: List[SheetCut] = []
    normalized: List[Tuple[SheetCut, float, float]] = []

    for c in cuts:
        w, l = c.width_in, c.length_in
        fits_normal = w <= sheet_width_in + 1e-6 and l <= sheet_length_in + 1e-6
        fits_rot = l <= sheet_width_in + 1e-6 and w <= sheet_length_in + 1e-6
        if not fits_normal and not fits_rot:
            oversized.append(c)
            continue
        # Orient so length runs along sheet_length_in when possible, or taller side along shelf
        if fits_normal and fits_rot:
            pw, pl = (min(w, l), max(w, l)) if sheet_width_in <= sheet_length_in else (max(w, l), min(w, l))
        elif fits_normal:
            pw, pl = w, l
        else:
            pw, pl = l, w
        normalized.append((c, pw, pl))

    normalized.sort(key=lambda item: item[2], reverse=True)

    # Each sheet is a list of shelves: [shelf_y_used, shelf_height, x_cursor]
    sheets_state: List[dict] = []
    for cut, pw, pl in normalized:
        placed = False
        for sh in sheets_state:
            for shelf in sh["shelves"]:
                x_need = pw + (kerf_in if shelf["count"] > 0 else 0.0)
                if shelf["x"] + x_need <= sheet_width_in + 1e-6 and pl <= shelf["h"] + 1e-6:
                    shelf["x"] += x_need
                    shelf["count"] += 1
                    sh["cuts"].append(cut)
                    sh["area"] += pw * pl
                    placed = True
                    break
            if placed:
                break
            y_need = pl + (kerf_in if sh["shelves"] else 0.0)
            if sh["y"] + y_need <= sheet_length_in + 1e-6 and pw <= sheet_width_in + 1e-6:
                sh["shelves"].append({"h": pl, "x": pw, "count": 1})
                sh["y"] += y_need
                sh["cuts"].append(cut)
                sh["area"] += pw * pl
                placed = True
                break
        if not placed:
            sheets_state.append(
                {
                    "shelves": [{"h": pl, "x": pw, "count": 1}],
                    "y": pl,
                    "cuts": [cut],
                    "area": pw * pl,
                }
            )

    total_area = sheet_width_in * sheet_length_in
    packed: List[PackedSheet] = []
    for sh in sheets_state:
        waste = max(0.0, 100.0 * (1.0 - sh["area"] / total_area)) if total_area > 0 else 0.0
        packed.append(
            PackedSheet(
                sheet_width_in=sheet_width_in,
                sheet_length_in=sheet_length_in,
                cuts=sh["cuts"],
                used_area_sq_in=sh["area"],
                waste_pct=waste,
            )
        )
    return packed, oversized


def format_cut_plan_report(
    linear_groups: Dict[str, Tuple[List[PackedBoard], List[LinearCut]]],
    sheet_groups: Dict[str, Tuple[List[PackedSheet], List[SheetCut]]],
    kerf_in: float,
) -> str:
    """Format a human-readable cut-list and shopping-list report."""
    lines: List[str] = [f'=== Cut List & Kerf Plan (Blade Kerf: {kerf_in:g}") ===', ""]

    if not linear_groups and not sheet_groups:
        lines.append("No lumber or sheet stock bodies found in the active design.")
        return "\n".join(lines)

    for group_name, (boards, oversized) in linear_groups.items():
        lines.append(f"[{group_name}] -> {len(boards)} stock board(s) needed")
        for idx, b in enumerate(boards, 1):
            cut_str = " + ".join(f'{c.length_in:g}"' for c in b.cuts)
            lines.append(
                f'  Board #{idx} ({b.stock_length_in:g}"): {cut_str} '
                f'| kerf: {b.kerf_loss_in:g}" | offcut: {b.offcut_in:g}"'
            )
        for oc in oversized:
            lines.append(f'  WARNING: "{oc.label}" ({oc.length_in:g}") exceeds stock length!')
        lines.append("")

    for group_name, (sheets, oversized) in sheet_groups.items():
        lines.append(f"[{group_name}] -> {len(sheets)} sheet(s) needed")
        for idx, s in enumerate(sheets, 1):
            cut_str = ", ".join(f'{c.width_in:g}"x{c.length_in:g}"' for c in s.cuts)
            lines.append(
                f'  Sheet #{idx} ({s.sheet_width_in:g}"x{s.sheet_length_in:g}"): '
                f"{cut_str} | waste: {s.waste_pct:.1f}%"
            )
        for oc in oversized:
            lines.append(
                f'  WARNING: "{oc.label}" ({oc.width_in:g}"x{oc.length_in:g}") exceeds max sheet!'
            )
        lines.append("")

    return "\n".join(lines).rstrip()
