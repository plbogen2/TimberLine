"""Pure-math 2D/3D layout planner for attaching a new board outward from a face."""

from dataclasses import dataclass
from typing import Tuple

import lumber_catalog

ATTACH_JOINT_TYPES = (
    "Butt (Flush)",
    "Miter (45°)",
    "Half-Lap",
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
    existing_lap_depth_cm: float
    new_board_length_cm: float
    miter_axis_is_u: bool
    miter_existing_tri: Tuple[Triangle2D, ...]
    miter_new_tri: Tuple[Triangle2D, ...]
    miter_plane_coord: float
    miter_span_cm: float
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
) -> AttachPlan:
    """Compute cross-section on ``face_bounds`` and outward extrusion along +Z."""
    if joint_type not in ATTACH_JOINT_TYPES:
        raise ValueError(f"Unsupported joint type: {joint_type}")
    if length_mode not in LENGTH_MODES:
        raise ValueError(f"Unsupported length mode: {length_mode}")

    u_min, v_min, u_max, v_max = face_bounds
    dim_along = lumber.thickness_cm if on_edge else lumber.width_cm
    dim_across = lumber.width_cm if on_edge else lumber.thickness_cm

    du = abs(edge_p0[0] - edge_p1[0])
    dv = abs(edge_p0[1] - edge_p1[1])

    if du < dv:
        # Edge runs along V; cross-section snaps to left (u_min) or right (u_max).
        u_edge = 0.5 * (edge_p0[0] + edge_p1[0])
        is_left = abs(u_edge - u_min) <= abs(u_edge - u_max)
        u0, u1 = (u_min, u_min + dim_along) if is_left else (u_max - dim_along, u_max)
        v0, v1 = (v_max - dim_across, v_max) if flip_along_edge else (v_min, v_min + dim_across)
        miter_axis_is_u = True
        miter_plane_coord = v0
        miter_span = dim_across
        edge_coord = u_min if is_left else u_max
        inward_coord = u_min + dim_along if is_left else u_max - dim_along
    else:
        # Edge runs along U; cross-section snaps to bottom (v_min) or top (v_max).
        v_edge = 0.5 * (edge_p0[1] + edge_p1[1])
        is_bottom = abs(v_edge - v_min) <= abs(v_edge - v_max)
        v0, v1 = (v_min, v_min + dim_along) if is_bottom else (v_max - dim_along, v_max)
        u0, u1 = (u_max - dim_across, u_max) if flip_along_edge else (u_min, u_min + dim_across)
        miter_axis_is_u = False
        miter_plane_coord = u0
        miter_span = dim_across
        edge_coord = v_min if is_bottom else v_max
        inward_coord = v_min + dim_along if is_bottom else v_max - dim_along

    rect = _norm_rect((u0, v0, u1, v1))

    outward_len = length_cm
    if length_mode == "Total Outer Span" and existing_depth_cm > 0:
        outward_len = max(0.1, length_cm - existing_depth_cm)

    if joint_type == "Butt (Flush)":
        return AttachPlan(
            cross_section_rect=rect,
            start_z_cm=0.0,
            extrude_z_cm=outward_len,
            existing_lap_depth_cm=0.0,
            new_board_length_cm=outward_len,
            miter_axis_is_u=miter_axis_is_u,
            miter_existing_tri=(),
            miter_new_tri=(),
            miter_plane_coord=miter_plane_coord,
            miter_span_cm=miter_span,
            joint_type=joint_type,
        )

    if joint_type == "Half-Lap":
        half_depth = existing_depth_cm / 2.0 if existing_depth_cm > 0 else 0.0
        total_new_len = outward_len + half_depth
        return AttachPlan(
            cross_section_rect=rect,
            start_z_cm=-half_depth,
            extrude_z_cm=total_new_len,
            existing_lap_depth_cm=half_depth,
            new_board_length_cm=total_new_len,
            miter_axis_is_u=miter_axis_is_u,
            miter_existing_tri=(),
            miter_new_tri=(),
            miter_plane_coord=miter_plane_coord,
            miter_span_cm=miter_span,
            joint_type=joint_type,
        )

    # Miter (45°): new board starts at z = -existing_depth_cm, both cut at 45 deg
    d = existing_depth_cm
    total_new_len = outward_len + d
    # In (coord, z) space: existing board has z in [-d, 0], new board overlaps [edge..inward]
    ex_tri = (
        (edge_coord, 0.0),
        (inward_coord, -d),
        (inward_coord, 0.0),
    )
    nw_tri = (
        (edge_coord, 0.0),
        (inward_coord, -d),
        (edge_coord, -d),
    )
    return AttachPlan(
        cross_section_rect=rect,
        start_z_cm=-d,
        extrude_z_cm=total_new_len,
        existing_lap_depth_cm=0.0,
        new_board_length_cm=total_new_len,
        miter_axis_is_u=miter_axis_is_u,
        miter_existing_tri=(ex_tri,),
        miter_new_tri=(nw_tri,),
        miter_plane_coord=miter_plane_coord,
        miter_span_cm=miter_span,
        joint_type=joint_type,
    )


def _norm_rect(r: Rect2D) -> Rect2D:
    x0, y0, x1, y1 = r
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
