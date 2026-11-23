"""Pure-math 2D layout planner for attaching a new board to an existing board."""

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
    """2D geometry plan in the target face's sketch coordinate system (cm)."""

    new_board_rect: Rect2D
    new_board_length_cm: float
    new_board_height_cm: float
    existing_miter_tri: Tuple[Triangle2D, ...]
    new_miter_tri: Tuple[Triangle2D, ...]
    lap_rect: Tuple[Rect2D, ...]
    joint_type: str


def compute_attach_plan(
    face_bounds: Rect2D,
    edge_p0: Tuple[float, float],
    edge_p1: Tuple[float, float],
    lumber: lumber_catalog.LumberSize,
    length_cm: float,
    on_edge: bool = True,
    joint_type: str = "Butt (Flush)",
    length_mode: str = "Exact Board Length",
    flip_along_edge: bool = False,
) -> AttachPlan:
    """Compute placement and corner cut geometry for attaching a board to a face+edge.

    In the target face's sketch space, the existing board lies inside
    ``face_bounds`` (z <= 0). The new board attaches at ``edge_p0 -> edge_p1``
    and extends outward away from ``face_bounds``, extruding in -Z by
    ``new_board_height_cm`` so both boards share the top face plane (z = 0).
    """
    if joint_type not in ATTACH_JOINT_TYPES:
        raise ValueError(f"Unsupported joint type: {joint_type}")
    if length_mode not in LENGTH_MODES:
        raise ValueError(f"Unsupported length mode: {length_mode}")

    u_min, v_min, u_max, v_max = face_bounds
    new_thick = lumber.thickness_cm if on_edge else lumber.width_cm
    new_height = lumber.width_cm if on_edge else lumber.thickness_cm

    du = abs(edge_p0[0] - edge_p1[0])
    dv = abs(edge_p0[1] - edge_p1[1])

    # Determine which side of face_bounds the selected edge is on.
    if du < dv:
        # Edge runs along V; existing board spans u_min..u_max, new board extends along U.
        u_edge = 0.5 * (edge_p0[0] + edge_p1[0])
        is_left = abs(u_edge - u_min) <= abs(u_edge - u_max)
        existing_span = u_max - u_min
        v_anchor = v_max if flip_along_edge else v_min
        v_sign = -1.0 if flip_along_edge else 1.0

        board_len = length_cm
        if joint_type == "Butt (Flush)" and length_mode == "Total Outer Span":
            board_len = max(0.1, length_cm - existing_span)

        if joint_type == "Butt (Flush)":
            if is_left:
                rect = (u_min - board_len, v_anchor, u_min, v_anchor + v_sign * new_thick)
            else:
                rect = (u_max, v_anchor, u_max + board_len, v_anchor + v_sign * new_thick)
            return AttachPlan(
                _norm_rect(rect), board_len, new_height, (), (), (), joint_type
            )

        # Miter (45°) or Half-Lap: new board overlaps existing board by existing_span
        overlap = existing_span
        if is_left:
            rect = (u_max - board_len, v_anchor, u_max, v_anchor + v_sign * new_thick)
            lap = (u_min, v_anchor, u_max, v_anchor + v_sign * new_thick)
            if joint_type == "Miter (45°)":
                # Existing corner (u_min..u_max, v_anchor..v_anchor + v_sign*new_thick)
                ex_tri = (
                    (u_min, v_anchor),
                    (u_max, v_anchor + v_sign * new_thick),
                    (u_min, v_anchor + v_sign * new_thick),
                )
                nw_tri = (
                    (u_min, v_anchor),
                    (u_max, v_anchor),
                    (u_max, v_anchor + v_sign * new_thick),
                )
                return AttachPlan(
                    _norm_rect(rect), board_len, new_height, (ex_tri,), (nw_tri,), (), joint_type
                )
        else:
            rect = (u_min, v_anchor, u_min + board_len, v_anchor + v_sign * new_thick)
            lap = (u_min, v_anchor, u_max, v_anchor + v_sign * new_thick)
            if joint_type == "Miter (45°)":
                ex_tri = (
                    (u_max, v_anchor),
                    (u_min, v_anchor + v_sign * new_thick),
                    (u_max, v_anchor + v_sign * new_thick),
                )
                nw_tri = (
                    (u_max, v_anchor),
                    (u_min, v_anchor),
                    (u_min, v_anchor + v_sign * new_thick),
                )
                return AttachPlan(
                    _norm_rect(rect), board_len, new_height, (ex_tri,), (nw_tri,), (), joint_type
                )

        return AttachPlan(
            _norm_rect(rect), board_len, new_height, (), (), (_norm_rect(lap),), joint_type
        )

    # Edge runs along U; existing board spans v_min..v_max, new board extends along V.
    v_edge = 0.5 * (edge_p0[1] + edge_p1[1])
    is_bottom = abs(v_edge - v_min) <= abs(v_edge - v_max)
    existing_span = v_max - v_min
    u_anchor = u_max if flip_along_edge else u_min
    u_sign = -1.0 if flip_along_edge else 1.0

    board_len = length_cm
    if joint_type == "Butt (Flush)" and length_mode == "Total Outer Span":
        board_len = max(0.1, length_cm - existing_span)

    if joint_type == "Butt (Flush)":
        if is_bottom:
            rect = (u_anchor, v_min - board_len, u_anchor + u_sign * new_thick, v_min)
        else:
            rect = (u_anchor, v_max, u_anchor + u_sign * new_thick, v_max + board_len)
        return AttachPlan(
            _norm_rect(rect), board_len, new_height, (), (), (), joint_type
        )

    if is_bottom:
        rect = (u_anchor, v_max - board_len, u_anchor + u_sign * new_thick, v_max)
        lap = (u_anchor, v_min, u_anchor + u_sign * new_thick, v_max)
        if joint_type == "Miter (45°)":
            ex_tri = (
                (u_anchor, v_min),
                (u_anchor + u_sign * new_thick, v_max),
                (u_anchor + u_sign * new_thick, v_min),
            )
            nw_tri = (
                (u_anchor, v_min),
                (u_anchor, v_max),
                (u_anchor + u_sign * new_thick, v_max),
            )
            return AttachPlan(
                _norm_rect(rect), board_len, new_height, (ex_tri,), (nw_tri,), (), joint_type
            )
    else:
        rect = (u_anchor, v_min, u_anchor + u_sign * new_thick, v_min + board_len)
        lap = (u_anchor, v_min, u_anchor + u_sign * new_thick, v_max)
        if joint_type == "Miter (45°)":
            ex_tri = (
                (u_anchor, v_max),
                (u_anchor + u_sign * new_thick, v_min),
                (u_anchor + u_sign * new_thick, v_max),
            )
            nw_tri = (
                (u_anchor, v_max),
                (u_anchor, v_min),
                (u_anchor + u_sign * new_thick, v_min),
            )
            return AttachPlan(
                _norm_rect(rect), board_len, new_height, (ex_tri,), (nw_tri,), (), joint_type
            )

    return AttachPlan(
        _norm_rect(rect), board_len, new_height, (), (), (_norm_rect(lap),), joint_type
    )


def _norm_rect(r: Rect2D) -> Rect2D:
    x0, y0, x1, y1 = r
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
