"""Pure-math 2D/3D layout planner for attaching a new board outward from a face."""

import math
from dataclasses import dataclass
from typing import Tuple

import lumber_catalog

ATTACH_JOINT_TYPES = (
    "Butt (Flush)",
    "Half-Lap",
    "Rabbet",
    "Dado / Groove",
    "Miter",
)

LENGTH_MODES = (
    "Exact Board Length",
    "Total Outer Span",
)

Rect2D = Tuple[float, float, float, float]  # (u0, v0, u1, v1)
Triangle2D = Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]


@dataclass(frozen=True)
class AttachPlan:
    """Geometry plan in the target face's sketch coordinates (cm).

    The selected face sits at ``z = 0``, with its outward normal along ``+Z``.
    The existing board lies behind the face (``z in [-existing_depth_cm, 0]``).
    """

    cross_section_rect: Rect2D
    start_z_cm: float
    extrude_z_cm: float
    existing_cut_depth_cm: float
    new_board_length_cm: float
    miter_axis_is_u: bool
    miter_existing_tri: Tuple[Triangle2D, ...]
    miter_new_tri: Tuple[Triangle2D, ...]
    miter_plane_coord: float
    miter_span_cm: float
    outer_angle_deg: float
    joint_type: str


def compute_attach_plan(
    face_bounds: Rect2D,
    edge_p0: Tuple[float, float],
    edge_p1: Tuple[float, float],
    lumber: lumber_catalog.LumberSize,
    length_cm: float,
    existing_depth_cm: float,
    on_edge: bool = True,
    joint_type: str = "Butt (Flush)",
    length_mode: str = "Exact Board Length",
    flip_along_edge: bool = False,
    joint_depth_cm: float = 0.0,
    offset_cm: float = 0.0,
    outer_angle_deg: float = 90.0,
) -> AttachPlan:
    """Compute cross-section on ``face_bounds`` and outward extrusion along +Z."""
    if joint_type not in ATTACH_JOINT_TYPES:
        raise ValueError(f"Unsupported joint type: {joint_type}")
    if length_mode not in LENGTH_MODES:
        raise ValueError(f"Unsupported length mode: {length_mode}")
    if joint_type == "Miter" and not (10.0 <= outer_angle_deg <= 170.0):
        raise ValueError("Miter outer angle must be between 10 and 170 degrees.")

    u_min, v_min, u_max, v_max = face_bounds
    dim_along = lumber.thickness_cm if on_edge else lumber.width_cm
    dim_across = lumber.width_cm if on_edge else lumber.thickness_cm
    eff_offset = max(0.0, offset_cm) if joint_type == "Dado / Groove" else 0.0

    du = abs(edge_p0[0] - edge_p1[0])
    dv = abs(edge_p0[1] - edge_p1[1])

    if du < dv:
        u_edge = 0.5 * (edge_p0[0] + edge_p1[0])
        is_left = abs(u_edge - u_min) <= abs(u_edge - u_max)
        if is_left:
            u0, u1 = u_min + eff_offset, u_min + eff_offset + dim_along
            edge_coord, inward_coord = u_min, u_min + dim_along
        else:
            u0, u1 = u_max - eff_offset - dim_along, u_max - eff_offset
            edge_coord, inward_coord = u_max, u_max - dim_along
        v0, v1 = (
            (v_max - dim_across, v_max)
            if flip_along_edge
            else (v_min, v_min + dim_across)
        )
        miter_axis_is_u = True
        miter_plane_coord = v0
        miter_span = dim_across
    else:
        v_edge = 0.5 * (edge_p0[1] + edge_p1[1])
        is_bottom = abs(v_edge - v_min) <= abs(v_edge - v_max)
        if is_bottom:
            v0, v1 = v_min + eff_offset, v_min + eff_offset + dim_along
            edge_coord, inward_coord = v_min, v_min + dim_along
        else:
            v0, v1 = v_max - eff_offset - dim_along, v_max - eff_offset
            edge_coord, inward_coord = v_max, v_max - dim_along
        u0, u1 = (
            (u_max - dim_across, u_max)
            if flip_along_edge
            else (u_min, u_min + dim_across)
        )
        miter_axis_is_u = False
        miter_plane_coord = u0
        miter_span = dim_across

    rect = _norm_rect((u0, v0, u1, v1))

    outward_len = length_cm
    if length_mode == "Total Outer Span" and existing_depth_cm > 0:
        outward_len = max(0.1, length_cm - existing_depth_cm)

    if joint_type == "Butt (Flush)":
        return AttachPlan(
            cross_section_rect=rect,
            start_z_cm=0.0,
            extrude_z_cm=outward_len,
            existing_cut_depth_cm=0.0,
            new_board_length_cm=outward_len,
            miter_axis_is_u=miter_axis_is_u,
            miter_existing_tri=(),
            miter_new_tri=(),
            miter_plane_coord=miter_plane_coord,
            miter_span_cm=miter_span,
            outer_angle_deg=outer_angle_deg,
            joint_type=joint_type,
        )

    if joint_type in ("Half-Lap", "Rabbet", "Dado / Groove"):
        if joint_depth_cm > 0:
            cut_depth = joint_depth_cm
        elif joint_type == "Half-Lap" and existing_depth_cm > 0:
            cut_depth = existing_depth_cm / 2.0
        else:
            cut_depth = lumber_catalog.inches_to_cm(0.375)

        total_new_len = outward_len + cut_depth
        return AttachPlan(
            cross_section_rect=rect,
            start_z_cm=-cut_depth,
            extrude_z_cm=total_new_len,
            existing_cut_depth_cm=cut_depth,
            new_board_length_cm=total_new_len,
            miter_axis_is_u=miter_axis_is_u,
            miter_existing_tri=(),
            miter_new_tri=(),
            miter_plane_coord=miter_plane_coord,
            miter_span_cm=miter_span,
            outer_angle_deg=outer_angle_deg,
            joint_type=joint_type,
        )

    # Miter with configurable outer_angle_deg (default 90 deg -> 45 deg per board)
    half_angle_rad = math.radians(outer_angle_deg / 2.0)
    cut_depth = dim_along * math.tan(half_angle_rad)
    if existing_depth_cm > 0:
        cut_depth = min(cut_depth, existing_depth_cm)
    total_new_len = outward_len + cut_depth
    ex_tri = (
        (edge_coord, 0.0),
        (inward_coord, -cut_depth),
        (inward_coord, 0.0),
    )
    nw_tri = (
        (edge_coord, 0.0),
        (inward_coord, -cut_depth),
        (edge_coord, -cut_depth),
    )
    return AttachPlan(
        cross_section_rect=rect,
        start_z_cm=-cut_depth,
        extrude_z_cm=total_new_len,
        existing_cut_depth_cm=0.0,
        new_board_length_cm=total_new_len,
        miter_axis_is_u=miter_axis_is_u,
        miter_existing_tri=(ex_tri,),
        miter_new_tri=(nw_tri,),
        miter_plane_coord=miter_plane_coord,
        miter_span_cm=miter_span,
        outer_angle_deg=outer_angle_deg,
        joint_type=joint_type,
    )


def _norm_rect(r: Rect2D) -> Rect2D:
    x0, y0, x1, y1 = r
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
