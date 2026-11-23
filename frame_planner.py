"""Pure-math layout planner for assembled 4-sided rectangular wood frames."""

from dataclasses import dataclass
from typing import List, Tuple

import lumber_catalog

CORNER_STYLES = (
    "Butt (Long Rails Full)",
    "Butt (Short Rails Full)",
    "Mitered (45°)",
    "Half-Lap Corners",
)

Rect2D = Tuple[float, float, float, float]  # (x0, y0, x1, y1) in cm


@dataclass(frozen=True)
class FrameMember:
    """One board in a rectangular frame (in cm, relative to frame origin)."""

    name: str
    x0_cm: float
    y0_cm: float
    dx_cm: float
    dy_cm: float
    dz_cm: float
    miter_triangles_xy: Tuple[Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]], ...] = ()
    lap_cuts_xy: Tuple[Rect2D, ...] = ()
    lap_from_top: bool = True


def compute_frame_members(
    lumber: lumber_catalog.LumberSize,
    outer_length_cm: float,
    outer_width_cm: float,
    on_edge: bool = True,
    corner_style: str = "Butt (Long Rails Full)",
) -> List[FrameMember]:
    """Compute the 4 boards of a rectangular frame with exact joinery dimensions.

    ``outer_length_cm`` runs along +X, ``outer_width_cm`` runs along +Y, and
    board height runs along +Z.
    """
    if corner_style not in CORNER_STYLES:
        raise ValueError(f"Unsupported corner style: {corner_style}")

    # Cross-section in frame plane (XY) vs vertical height (Z)
    thick_xy = lumber.thickness_cm if on_edge else lumber.width_cm
    height_z = lumber.width_cm if on_edge else lumber.thickness_cm

    if outer_length_cm <= 2.0 * thick_xy or outer_width_cm <= 2.0 * thick_xy:
        raise ValueError("Outer frame dimensions must exceed twice the board thickness.")

    if corner_style == "Butt (Long Rails Full)":
        short_len = outer_width_cm - 2.0 * thick_xy
        return [
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, outer_length_cm),
                0.0, 0.0, outer_length_cm, thick_xy, height_z,
            ),
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, outer_length_cm),
                0.0, outer_width_cm - thick_xy, outer_length_cm, thick_xy, height_z,
            ),
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, short_len),
                0.0, thick_xy, thick_xy, short_len, height_z,
            ),
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, short_len),
                outer_length_cm - thick_xy, thick_xy, thick_xy, short_len, height_z,
            ),
        ]

    if corner_style == "Butt (Short Rails Full)":
        long_len = outer_length_cm - 2.0 * thick_xy
        return [
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, long_len),
                thick_xy, 0.0, long_len, thick_xy, height_z,
            ),
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, long_len),
                thick_xy, outer_width_cm - thick_xy, long_len, thick_xy, height_z,
            ),
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, outer_width_cm),
                0.0, 0.0, thick_xy, outer_width_cm, height_z,
            ),
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, outer_width_cm),
                outer_length_cm - thick_xy, 0.0, thick_xy, outer_width_cm, height_z,
            ),
        ]

    if corner_style == "Mitered (45°)":
        t = thick_xy
        L = outer_length_cm
        W = outer_width_cm
        return [
            # Bottom X rail: mitered at inner corners (t, t) and (L-t, t)
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, L),
                0.0, 0.0, L, t, height_z,
                miter_triangles_xy=(
                    ((0.0, t), (t, t), (0.0, 0.0)),
                    ((L - t, t), (L, t), (L, 0.0)),
                ),
            ),
            # Top X rail: mitered at inner corners (t, W-t) and (L-t, W-t)
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, L),
                0.0, W - t, L, t, height_z,
                miter_triangles_xy=(
                    ((0.0, W - t), (t, W - t), (0.0, W)),
                    ((L - t, W - t), (L, W - t), (L, W)),
                ),
            ),
            # Left Y rail: mitered at inner corners (t, t) and (t, W-t)
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, W),
                0.0, 0.0, t, W, height_z,
                miter_triangles_xy=(
                    ((t, 0.0), (t, t), (0.0, 0.0)),
                    ((t, W - t), (t, W), (0.0, W)),
                ),
            ),
            # Right Y rail: mitered at inner corners (L-t, t) and (L-t, W-t)
            FrameMember(
                lumber_catalog.format_component_name(lumber.nominal, W),
                L - t, 0.0, t, W, height_z,
                miter_triangles_xy=(
                    ((L - t, 0.0), (L - t, t), (L, 0.0)),
                    ((L - t, W - t), (L - t, W), (L, W)),
                ),
            ),
        ]

    # Half-Lap Corners: X rails cut from top half, Y rails cut from bottom half
    t = thick_xy
    L = outer_length_cm
    W = outer_width_cm
    return [
        FrameMember(
            lumber_catalog.format_component_name(lumber.nominal, L),
            0.0, 0.0, L, t, height_z,
            lap_cuts_xy=((0.0, 0.0, t, t), (L - t, 0.0, L, t)),
            lap_from_top=True,
        ),
        FrameMember(
            lumber_catalog.format_component_name(lumber.nominal, L),
            0.0, W - t, L, t, height_z,
            lap_cuts_xy=((0.0, W - t, t, W), (L - t, W - t, L, W)),
            lap_from_top=True,
        ),
        FrameMember(
            lumber_catalog.format_component_name(lumber.nominal, W),
            0.0, 0.0, t, W, height_z,
            lap_cuts_xy=((0.0, 0.0, t, t), (0.0, W - t, t, W)),
            lap_from_top=False,
        ),
        FrameMember(
            lumber_catalog.format_component_name(lumber.nominal, W),
            L - t, 0.0, t, W, height_z,
            lap_cuts_xy=((L - t, 0.0, L, t), (L - t, W - t, L, W)),
            lap_from_top=False,
        ),
    ]
