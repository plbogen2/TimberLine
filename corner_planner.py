"""Pure-math 3D overlap planner for converting an existing 2-board corner into a joint."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

CORNER_CONVERT_TYPES = (
    "Half-Lap",
    "Miter (45°)",
    "Bridle (A=Slot, B=Tenon)",
    "Butt (Trim A to B)",
    "Butt (Trim B to A)",
)

AXIS_CHOICES = ("Auto (Thinnest)", "X", "Y", "Z")

Box3D = Tuple[float, float, float, float, float, float]  # (x0, y0, z0, x1, y1, z1)
Point2D = Tuple[float, float]


@dataclass(frozen=True)
class MiterPrismSpec:
    """Triangular prism cut in the (u_axis, v_axis) plane extruded along extrude_axis."""

    u_axis: int  # 0=X, 1=Y, 2=Z
    v_axis: int
    extrude_axis: int
    tri_2d: Tuple[Point2D, Point2D, Point2D]
    ext_min: float
    ext_max: float


@dataclass(frozen=True)
class CornerCutPlan:
    joint_type: str
    a_boxes: Tuple[Box3D, ...]
    b_boxes: Tuple[Box3D, ...]
    a_miter: Optional[MiterPrismSpec] = None
    b_miter: Optional[MiterPrismSpec] = None
    extend_a_box: Optional[Box3D] = None
    extend_b_box: Optional[Box3D] = None
    use_boolean_trim_a: bool = False
    use_boolean_trim_b: bool = False


def compute_overlap_box(box_a: Box3D, box_b: Box3D, eps: float = 1e-4) -> Optional[Box3D]:
    """Return the 3D intersection box of ``box_a`` and ``box_b``, or ``None``."""
    x0 = max(box_a[0], box_b[0])
    y0 = max(box_a[1], box_b[1])
    z0 = max(box_a[2], box_b[2])
    x1 = min(box_a[3], box_b[3])
    y1 = min(box_a[4], box_b[4])
    z1 = min(box_a[5], box_b[5])
    if x1 - x0 <= eps or y1 - y0 <= eps or z1 - z0 <= eps:
        return None
    return (x0, y0, z0, x1, y1, z1)


def compute_corner_junction(
    box_a: Box3D, box_b: Box3D, touch_eps: float = 0.05
) -> Tuple[Optional[Box3D], Optional[Box3D], Optional[Box3D]]:
    """Return ``(junction_box, extend_a_box, extend_b_box)`` for overlapping or touching boards."""
    overlap = compute_overlap_box(box_a, box_b)
    if overlap is not None:
        return (overlap, None, None)

    for ax in (0, 1, 2):
        other = [i for i in (0, 1, 2) if i != ax]
        o0_lo = max(box_a[other[0]], box_b[other[0]])
        o0_hi = min(box_a[other[0] + 3], box_b[other[0] + 3])
        o1_lo = max(box_a[other[1]], box_b[other[1]])
        o1_hi = min(box_a[other[1] + 3], box_b[other[1] + 3])
        if o0_hi - o0_lo <= 1e-4 or o1_hi - o1_lo <= 1e-4:
            continue

        # Check if A ends where B starts, or B ends where A starts
        if abs(box_a[ax + 3] - box_b[ax]) <= touch_eps or abs(box_b[ax + 3] - box_a[ax]) <= touch_eps:
            span_a = box_a[ax + 3] - box_a[ax]
            span_b = box_b[ax + 3] - box_b[ax]
            if span_a <= span_b:
                # B butts into A's side; extend B across A
                vals = [0.0] * 6
                vals[other[0]], vals[other[0] + 3] = o0_lo, o0_hi
                vals[other[1]], vals[other[1] + 3] = o1_lo, o1_hi
                vals[ax], vals[ax + 3] = box_a[ax], box_a[ax + 3]
                junc: Box3D = (vals[0], vals[1], vals[2], vals[3], vals[4], vals[5])
                return (junc, None, junc)
            vals = [0.0] * 6
            vals[other[0]], vals[other[0] + 3] = o0_lo, o0_hi
            vals[other[1]], vals[other[1] + 3] = o1_lo, o1_hi
            vals[ax], vals[ax + 3] = box_b[ax], box_b[ax + 3]
            junc = (vals[0], vals[1], vals[2], vals[3], vals[4], vals[5])
            return (junc, junc, None)

    return (None, None, None)


def _pick_split_axis(overlap: Box3D, axis_choice: str) -> int:
    if axis_choice == "X":
        return 0
    if axis_choice == "Y":
        return 1
    if axis_choice == "Z":
        return 2
    spans = (overlap[3] - overlap[0], overlap[4] - overlap[1], overlap[5] - overlap[2])
    return min(range(3), key=lambda i: spans[i])


def _replace_axis(box: Box3D, axis: int, lo: float, hi: float) -> Box3D:
    vals = list(box)
    vals[axis] = lo
    vals[axis + 3] = hi
    return (vals[0], vals[1], vals[2], vals[3], vals[4], vals[5])


def compute_corner_cuts(
    box_a: Box3D,
    box_b: Box3D,
    joint_type: str = "Half-Lap",
    axis_choice: str = "Auto (Thinnest)",
) -> CornerCutPlan:
    """Compute the exact 3D cuts on Board A and Board B to convert their corner."""
    if joint_type not in CORNER_CONVERT_TYPES:
        raise ValueError(f"Unsupported corner joint type: {joint_type}")

    if joint_type == "Butt (Trim A to B)":
        return CornerCutPlan(joint_type, (), (), use_boolean_trim_a=True)
    if joint_type == "Butt (Trim B to A)":
        return CornerCutPlan(joint_type, (), (), use_boolean_trim_b=True)

    overlap, ext_a, ext_b = compute_corner_junction(box_a, box_b)
    if overlap is None:
        raise ValueError("Boards must overlap or touch at the corner to convert.")

    axis = _pick_split_axis(overlap, axis_choice)
    lo = overlap[axis]
    hi = overlap[axis + 3]
    span = hi - lo

    if joint_type == "Half-Lap":
        mid = 0.5 * (lo + hi)
        return CornerCutPlan(
            joint_type=joint_type,
            a_boxes=(_replace_axis(overlap, axis, mid, hi),),
            b_boxes=(_replace_axis(overlap, axis, lo, mid),),
            extend_a_box=ext_a,
            extend_b_box=ext_b,
        )

    if joint_type == "Bridle (A=Slot, B=Tenon)":
        t1 = lo + span / 3.0
        t2 = lo + 2.0 * span / 3.0
        return CornerCutPlan(
            joint_type=joint_type,
            a_boxes=(_replace_axis(overlap, axis, t1, t2),),
            b_boxes=(
                _replace_axis(overlap, axis, lo, t1),
                _replace_axis(overlap, axis, t2, hi),
            ),
            extend_a_box=ext_a,
            extend_b_box=ext_b,
        )

    # Miter (45°): cut complementary diagonal triangles in the 2 axes != split_axis
    other = [i for i in (0, 1, 2) if i != axis]
    u_ax, v_ax = other[0], other[1]
    u0, u1 = overlap[u_ax], overlap[u_ax + 3]
    v0, v1 = overlap[v_ax], overlap[v_ax + 3]

    # Pick diagonal connecting the outer corner (where A and B both end) to inner corner
    a_u_center = 0.5 * (box_a[u_ax] + box_a[u_ax + 3])
    b_v_center = 0.5 * (box_b[v_ax] + box_b[v_ax + 3])
    ov_u_center = 0.5 * (u0 + u1)
    ov_v_center = 0.5 * (v0 + v1)

    # Outer corner of A along u is opposite A's body center; same for B along v
    u_outer = u1 if a_u_center <= ov_u_center else u0
    u_inner = u0 if u_outer == u1 else u1
    v_outer = v1 if b_v_center <= ov_v_center else v0
    v_inner = v0 if v_outer == v1 else v1

    tri_a = ((u_outer, v_outer), (u_inner, v_inner), (u_outer, v_inner))
    tri_b = ((u_outer, v_outer), (u_inner, v_inner), (u_inner, v_outer))

    return CornerCutPlan(
        joint_type=joint_type,
        a_boxes=(),
        b_boxes=(),
        a_miter=MiterPrismSpec(u_ax, v_ax, axis, tri_a, lo, hi),
        b_miter=MiterPrismSpec(u_ax, v_ax, axis, tri_b, lo, hi),
        extend_a_box=ext_a,
        extend_b_box=ext_b,
    )
