"""Pure-math 3D planner for filling an opening between boards with a panel."""

from dataclasses import dataclass
import math
from typing import List, Tuple

import lumber_catalog

PANEL_PLANES = (
    "Auto (Opening Plane)",
    "XY (Z-Normal)",
    "XZ (Y-Normal)",
    "YZ (X-Normal)",
)

PANEL_ALIGNMENTS = (
    "Centered (Dado / Groove)",
    "Flush Front (+Normal Rabbet)",
    "Flush Back (-Normal Rabbet)",
)

Box3D = Tuple[float, float, float, float, float, float]  # (x0, y0, z0, x1, y1, z1)
Point2D = Tuple[float, float]


@dataclass(frozen=True)
class PanelPlan:
    panel_box: Box3D
    polygon_uv: Tuple[Point2D, ...]
    normal_axis: int
    width_in: float
    length_in: float
    fits_max_sheet: bool


def _pick_normal_axis(boxes: List[Box3D], plane_choice: str) -> int:
    if plane_choice == "YZ (X-Normal)":
        return 0
    if plane_choice == "XZ (Y-Normal)":
        return 1
    if plane_choice == "XY (Z-Normal)":
        return 2

    # Auto: pick the axis with the smallest overall frame thickness (no inner gap)
    best_axis = 2
    best_span = float("inf")
    for ax in (0, 1, 2):
        lo = min(b[ax] for b in boxes)
        hi = max(b[ax + 3] for b in boxes)
        span = hi - lo
        if span < best_span:
            best_span = span
            best_axis = ax
    return best_axis


def _compute_span_along_axis(
    boxes: List[Box3D], ax: int, depth_cm: float
) -> Tuple[float, float]:
    outer_lo = min(b[ax] for b in boxes)
    outer_hi = max(b[ax + 3] for b in boxes)
    mid = 0.5 * (outer_lo + outer_hi)

    # Boards strictly on the low side vs high side of the opening
    low_boards = [b for b in boxes if b[ax + 3] <= mid + 1e-4]
    high_boards = [b for b in boxes if b[ax] >= mid - 1e-4]

    inner_lo = max((b[ax + 3] for b in low_boards), default=outer_lo)
    inner_hi = min((b[ax] for b in high_boards), default=outer_hi)

    if low_boards and high_boards and inner_hi > inner_lo + 1e-4:
        return (inner_lo - depth_cm, inner_hi + depth_cm)
    if low_boards and not high_boards:
        return (inner_lo - depth_cm, outer_hi)
    if high_boards and not low_boards:
        return (outer_lo, inner_hi + depth_cm)
    return (outer_lo, outer_hi)


def compute_panel_plan(
    board_boxes: List[Box3D],
    sheet: lumber_catalog.SheetThickness,
    depth_cm: float = 0.0,
    plane_choice: str = "Auto (Opening Plane)",
    alignment: str = "Centered (Dado / Groove)",
) -> PanelPlan:
    """Compute the 3D panel box filling the space between ``board_boxes``."""
    if len(board_boxes) < 2:
        raise ValueError("Select at least 2 surrounding boards to fill a panel.")
    if plane_choice not in PANEL_PLANES:
        raise ValueError(f"Unsupported panel plane: {plane_choice}")
    if alignment not in PANEL_ALIGNMENTS:
        raise ValueError(f"Unsupported panel alignment: {alignment}")

    n_ax = _pick_normal_axis(board_boxes, plane_choice)
    w_lo = min(b[n_ax] for b in board_boxes)
    w_hi = max(b[n_ax + 3] for b in board_boxes)
    t = sheet.thickness_cm

    if alignment == "Flush Front (+Normal Rabbet)":
        w0, w1 = w_hi - t, w_hi
    elif alignment == "Flush Back (-Normal Rabbet)":
        w0, w1 = w_lo, w_lo + t
    else:
        w_mid = 0.5 * (w_lo + w_hi)
        w0, w1 = w_mid - 0.5 * t, w_mid + 0.5 * t

    bounds_lo = [0.0, 0.0, 0.0]
    bounds_hi = [0.0, 0.0, 0.0]
    bounds_lo[n_ax] = w0
    bounds_hi[n_ax] = w1

    span_axes = [ax for ax in (0, 1, 2) if ax != n_ax]
    span_dims_in: List[float] = []
    for ax in span_axes:
        s0, s1 = _compute_span_along_axis(board_boxes, ax, max(0.0, depth_cm))
        bounds_lo[ax] = s0
        bounds_hi[ax] = s1
        span_dims_in.append(lumber_catalog.cm_to_inches(s1 - s0))

    w_in = min(span_dims_in)
    l_in = max(span_dims_in)
    fits = sheet.fits_in_sheet(w_in, l_in)

    box: Box3D = (
        bounds_lo[0],
        bounds_lo[1],
        bounds_lo[2],
        bounds_hi[0],
        bounds_hi[1],
        bounds_hi[2],
    )
    u_ax, v_ax = span_axes[0], span_axes[1]
    polygon_uv = _compute_polygon_uv(board_boxes, u_ax, v_ax, box, depth_cm)

    return PanelPlan(
        panel_box=box,
        polygon_uv=polygon_uv,
        normal_axis=n_ax,
        width_in=w_in,
        length_in=l_in,
        fits_max_sheet=fits,
    )


def _compute_polygon_uv(
    boxes: List[Box3D],
    u_ax: int,
    v_ax: int,
    rect_box: Box3D,
    depth_cm: float,
) -> Tuple[Point2D, ...]:
    """Return a rectangular footprint for <=4 axis-aligned boards, or an N-gon for 5+."""
    if len(boxes) <= 4:
        u0, v0 = rect_box[u_ax], rect_box[v_ax]
        u1, v1 = rect_box[u_ax + 3], rect_box[v_ax + 3]
        return ((u0, v0), (u1, v0), (u1, v1), (u0, v1))

    # Order board centers radially around centroid for hexagonal / polygonal frames
    centers = [
        (0.5 * (b[u_ax] + b[u_ax + 3]), 0.5 * (b[v_ax] + b[v_ax + 3]), b)
        for b in boxes
    ]
    cu = sum(c[0] for c in centers) / len(centers)
    cv = sum(c[1] for c in centers) / len(centers)
    ordered = sorted(centers, key=lambda c: math.atan2(c[1] - cv, c[0] - cu))

    verts: List[Point2D] = []
    for bx, by, b in ordered:
        dx, dy = bx - cu, by - cv
        dist = math.hypot(dx, dy) or 1.0
        half_wall = 0.5 * min(b[u_ax + 3] - b[u_ax], b[v_ax + 3] - b[v_ax])
        target_r = max(0.1, dist - half_wall + max(0.0, depth_cm))
        scale = target_r / dist
        verts.append((cu + dx * scale, cv + dy * scale))
    return tuple(verts)
