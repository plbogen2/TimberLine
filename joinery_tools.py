"""Pure-math 2D sketch layout helpers for common woodworking joinery."""

from typing import List, Tuple

Rect2D = Tuple[float, float, float, float]  # (u0, v0, u1, v1)
Point2D = Tuple[float, float]


def compute_edge_strip_rect(
    face_bounds: Rect2D,
    edge_p0: Point2D,
    edge_p1: Point2D,
    width: float,
    offset: float = 0.0,
    overcut: float = 0.01,
) -> Rect2D:
    """Compute a 2D cut rectangle parallel to a reference edge on a planar face.

    Used for Rabbet (offset=0), Half-Lap (offset=0, width=lap_length), and
    Dado/Groove (offset>0). ``overcut`` slightly extends the ends along the
    edge direction so cuts cleanly break through adjacent faces.
    """
    u_min, v_min, u_max, v_max = face_bounds
    du = abs(edge_p0[0] - edge_p1[0])
    dv = abs(edge_p0[1] - edge_p1[1])

    if du < dv:
        # Edge runs along V; cut steps inward along U.
        u_edge = 0.5 * (edge_p0[0] + edge_p1[0])
        if abs(u_edge - u_min) <= abs(u_edge - u_max):
            u0 = u_min + offset - (overcut if offset == 0.0 else 0.0)
            u1 = u_min + offset + width
        else:
            u0 = u_max - offset - width
            u1 = u_max - offset + (overcut if offset == 0.0 else 0.0)
        return (u0, v_min - overcut, u1, v_max + overcut)

    # Edge runs along U; cut steps inward along V.
    v_edge = 0.5 * (edge_p0[1] + edge_p1[1])
    if abs(v_edge - v_min) <= abs(v_edge - v_max):
        v0 = v_min + offset - (overcut if offset == 0.0 else 0.0)
        v1 = v_min + offset + width
    else:
        v0 = v_max - offset - width
        v1 = v_max - offset + (overcut if offset == 0.0 else 0.0)
    return (u_min - overcut, v0, u_max + overcut, v1)


def compute_board_reference_params(
    face_bounds: Rect2D,
    edge_p0: Point2D,
    edge_p1: Point2D,
    ref_bounds: Rect2D,
) -> Tuple[float, float]:
    """Compute ``(offset, width)`` on a face from a mating board's 2D bounds.

    Measures perpendicular to ``edge_p0 -> edge_p1`` so selecting a mating
    board auto-fills the exact rabbet width, dado offset+width, or lap length.
    """
    u_min, v_min, u_max, v_max = face_bounds
    ru_min, rv_min, ru_max, rv_max = ref_bounds
    du = abs(edge_p0[0] - edge_p1[0])
    dv = abs(edge_p0[1] - edge_p1[1])

    if du < dv:
        u_edge = 0.5 * (edge_p0[0] + edge_p1[0])
        width = max(0.0, ru_max - ru_min)
        if abs(u_edge - u_min) <= abs(u_edge - u_max):
            offset = max(0.0, ru_min - u_min)
        else:
            offset = max(0.0, u_max - ru_max)
        return (offset, width)

    v_edge = 0.5 * (edge_p0[1] + edge_p1[1])
    width = max(0.0, rv_max - rv_min)
    if abs(v_edge - v_min) <= abs(v_edge - v_max):
        offset = max(0.0, rv_min - v_min)
    else:
        offset = max(0.0, v_max - rv_max)
    return (offset, width)


def compute_centered_rect(
    face_bounds: Rect2D,
    short_dim: float,
    long_dim: float,
) -> Rect2D:
    """Compute a centered 2D rectangle aligned with the face's longer axis."""
    u_min, v_min, u_max, v_max = face_bounds
    u_center = 0.5 * (u_min + u_max)
    v_center = 0.5 * (v_min + v_max)
    face_u = u_max - u_min
    face_v = v_max - v_min

    if face_u >= face_v:
        half_u = 0.5 * long_dim
        half_v = 0.5 * short_dim
    else:
        half_u = 0.5 * short_dim
        half_v = 0.5 * long_dim

    return (
        u_center - half_u,
        v_center - half_v,
        u_center + half_u,
        v_center + half_v,
    )


def compute_tongue_shoulder_rects(
    face_bounds: Rect2D,
    tongue_thick: float,
    overcut: float = 0.01,
) -> Tuple[Rect2D, Rect2D]:
    """Compute the two shoulder cut rectangles leaving a centered tongue."""
    u_min, v_min, u_max, v_max = face_bounds
    face_u = u_max - u_min
    face_v = v_max - v_min
    if face_u >= face_v:
        v_mid = 0.5 * (v_min + v_max)
        half_t = 0.5 * tongue_thick
        return (
            (u_min - overcut, v_min - overcut, u_max + overcut, v_mid - half_t),
            (u_min - overcut, v_mid + half_t, u_max + overcut, v_max + overcut),
        )
    u_mid = 0.5 * (u_min + u_max)
    half_t = 0.5 * tongue_thick
    return (
        (u_min - overcut, v_min - overcut, u_mid - half_t, v_max + overcut),
        (u_mid + half_t, v_min - overcut, u_max + overcut, v_max + overcut),
    )


def compute_centered_groove_rect(
    face_bounds: Rect2D,
    groove_thick: float,
    overcut: float = 0.01,
) -> Rect2D:
    """Compute a centered full-length groove rectangle along the face's longer axis."""
    u_min, v_min, u_max, v_max = face_bounds
    face_u = u_max - u_min
    face_v = v_max - v_min
    if face_u >= face_v:
        v_mid = 0.5 * (v_min + v_max)
        half_t = 0.5 * groove_thick
        return (u_min - overcut, v_mid - half_t, u_max + overcut, v_mid + half_t)
    u_mid = 0.5 * (u_min + u_max)
    half_t = 0.5 * groove_thick
    return (u_mid - half_t, v_min - overcut, u_mid + half_t, v_max + overcut)


def compute_finger_cut_rects(
    face_bounds: Rect2D,
    count: int,
    cut_even: bool = True,
    overcut: float = 0.01,
) -> List[Rect2D]:
    """Divide the face's longer axis into ``count`` fingers and return cut rects."""
    if count <= 1:
        return []
    u_min, v_min, u_max, v_max = face_bounds
    face_u = u_max - u_min
    face_v = v_max - v_min
    rects: List[Rect2D] = []

    if face_u >= face_v:
        step = face_u / count
        for i in range(count):
            if (i % 2 == 0) == cut_even:
                x0 = u_min + i * step - (overcut if i == 0 else 0.0)
                x1 = u_min + (i + 1) * step + (overcut if i == count - 1 else 0.0)
                rects.append((x0, v_min - overcut, x1, v_max + overcut))
        return rects

    step = face_v / count
    for i in range(count):
        if (i % 2 == 0) == cut_even:
            y0 = v_min + i * step - (overcut if i == 0 else 0.0)
            y1 = v_min + (i + 1) * step + (overcut if i == count - 1 else 0.0)
            rects.append((u_min - overcut, y0, u_max + overcut, y1))
    return rects


def compute_dovetail_cut_polygons(
    face_bounds: Rect2D,
    count: int,
    depth: float,
    slope_ratio: float = 7.0,
    is_pins: bool = False,
    overcut: float = 0.01,
) -> List[List[Point2D]]:
    """Compute trapezoidal cut polygons for dovetail tails or pins along the long axis."""
    if count <= 0:
        return []
    u_min, v_min, u_max, v_max = face_bounds
    face_u = u_max - u_min
    face_v = v_max - v_min
    long_span = max(face_u, face_v)
    pitch = long_span / count
    flare = min(depth / slope_ratio, pitch * 0.2)
    polys: List[List[Point2D]] = []

    # Generate alternating trapezoidal waste pockets between tails/pins
    slots = count + 1 if not is_pins else count
    for i in range(slots):
        if not is_pins:
            # Cut pockets at outer ends and between tails
            c_left = -overcut if i == 0 else i * pitch - 0.25 * pitch
            c_right = long_span + overcut if i == count else i * pitch + 0.25 * pitch
            w_front_0 = max(-overcut, c_left - (0.0 if i == 0 else flare))
            w_front_1 = min(long_span + overcut, c_right + (0.0 if i == count else flare))
            w_back_0 = max(-overcut, c_left + (0.0 if i == 0 else flare))
            w_back_1 = min(long_span + overcut, c_right - (0.0 if i == count else flare))
        else:
            # Cut tail sockets between pins
            c_left = i * pitch + 0.25 * pitch
            c_right = i * pitch + 0.75 * pitch
            w_front_0 = c_left + flare
            w_front_1 = c_right - flare
            w_back_0 = c_left - flare
            w_back_1 = c_right + flare

        if face_u >= face_v:
            polys.append([
                (u_min + w_front_0, v_min - overcut),
                (u_min + w_front_1, v_min - overcut),
                (u_min + w_back_1, v_max + overcut),
                (u_min + w_back_0, v_max + overcut),
            ])
        else:
            polys.append([
                (u_min - overcut, v_min + w_front_0),
                (u_min - overcut, v_min + w_front_1),
                (u_max + overcut, v_min + w_back_1),
                (u_max + overcut, v_min + w_back_0),
            ])
    return polys


def compute_biscuit_slot_rects(
    face_bounds: Rect2D,
    count: int,
    edge_inset: float,
    slot_len: float,
    slot_thick: float,
) -> List[Rect2D]:
    """Compute centered rectangular biscuit slot profiles along the face's long axis."""
    centers = compute_dowel_centers(face_bounds, count, edge_inset)
    u_min, v_min, u_max, v_max = face_bounds
    face_u = u_max - u_min
    face_v = v_max - v_min
    rects: List[Rect2D] = []
    for cx, cy in centers:
        if face_u >= face_v:
            rects.append((
                cx - 0.5 * slot_len,
                cy - 0.5 * slot_thick,
                cx + 0.5 * slot_len,
                cy + 0.5 * slot_thick,
            ))
        else:
            rects.append((
                cx - 0.5 * slot_thick,
                cy - 0.5 * slot_len,
                cx + 0.5 * slot_thick,
                cy + 0.5 * slot_len,
            ))
    return rects


def compute_dowel_centers(
    face_bounds: Rect2D,
    count: int,
    edge_inset: float,
) -> List[Point2D]:
    """Compute evenly spaced dowel hole centers along the face's longer axis."""
    if count <= 0:
        return []
    u_min, v_min, u_max, v_max = face_bounds
    u_center = 0.5 * (u_min + u_max)
    v_center = 0.5 * (v_min + v_max)
    face_u = u_max - u_min
    face_v = v_max - v_min

    if count == 1:
        return [(u_center, v_center)]

    if face_u >= face_v:
        start = u_min + edge_inset
        end = u_max - edge_inset
        if end <= start:
            start, end = u_min, u_max
        step = (end - start) / (count - 1)
        return [(start + i * step, v_center) for i in range(count)]

    start = v_min + edge_inset
    end = v_max - edge_inset
    if end <= start:
        start, end = v_min, v_max
    step = (end - start) / (count - 1)
    return [(u_center, start + i * step) for i in range(count)]


def compute_pocket_hole_line_and_centers(
    face_bounds: Rect2D,
    edge_p0: Point2D,
    edge_p1: Point2D,
    setback: float,
    count: int,
    edge_inset: float,
) -> Tuple[Point2D, Point2D, Point2D, List[Point2D]]:
    """Compute setback line endpoints, inward-to-edge normal, and pocket centers.

    Returns ``(line_p0, line_p1, to_edge_dir_2d, centers)`` in sketch 2D space.
    """
    u_min, v_min, u_max, v_max = face_bounds
    du = abs(edge_p0[0] - edge_p1[0])
    dv = abs(edge_p0[1] - edge_p1[1])

    if du < dv:
        u_edge = 0.5 * (edge_p0[0] + edge_p1[0])
        if abs(u_edge - u_min) <= abs(u_edge - u_max):
            u_line = u_min + setback
            to_edge = (-1.0, 0.0)
        else:
            u_line = u_max - setback
            to_edge = (1.0, 0.0)

        if count <= 1:
            centers = [(u_line, 0.5 * (v_min + v_max))]
        else:
            v_start = v_min + edge_inset
            v_end = v_max - edge_inset
            if v_end <= v_start:
                v_start, v_end = v_min, v_max
            step = (v_end - v_start) / (count - 1)
            centers = [(u_line, v_start + i * step) for i in range(count)]
        return ((u_line, v_min), (u_line, v_max), to_edge, centers)

    v_edge = 0.5 * (edge_p0[1] + edge_p1[1])
    if abs(v_edge - v_min) <= abs(v_edge - v_max):
        v_line = v_min + setback
        to_edge = (0.0, -1.0)
    else:
        v_line = v_max - setback
        to_edge = (0.0, 1.0)

    if count <= 1:
        centers = [(0.5 * (u_min + u_max), v_line)]
    else:
        u_start = u_min + edge_inset
        u_end = u_max - edge_inset
        if u_end <= u_start:
            u_start, u_end = u_min, u_max
        step = (u_end - u_start) / (count - 1)
        centers = [(u_start + i * step, v_line) for i in range(count)]
    return ((u_min, v_line), (u_max, v_line), to_edge, centers)
