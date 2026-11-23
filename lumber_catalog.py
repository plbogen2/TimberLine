"""North American dimensional lumber catalog (PS 20-20 actual sizes).

Fusion 360's internal length unit is centimeters (cm). All actual dimensions
here are defined in inches and converted to cm via ``inches_to_cm``.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

INCH_TO_CM: float = 2.54
EASED_EDGE_RADIUS_IN: float = 0.125  # Standard 1/8" eased edge on S4S lumber


@dataclass(frozen=True)
class LumberSize:
    nominal: str
    category: str
    thickness_in: float
    width_in: float

    @property
    def thickness_cm(self) -> float:
        return self.thickness_in * INCH_TO_CM

    @property
    def width_cm(self) -> float:
        return self.width_in * INCH_TO_CM

    @property
    def label(self) -> str:
        return f'{self.nominal} ({_fmt_in(self.thickness_in)}" x {_fmt_in(self.width_in)}")'


def _fmt_in(value: float) -> str:
    """Format an inch dimension cleanly without trailing zeros."""
    return f"{value:g}"


def inches_to_cm(inches: float) -> float:
    """Convert inches to Fusion 360 internal units (centimeters)."""
    return inches * INCH_TO_CM


def cm_to_inches(cm: float) -> float:
    """Convert Fusion 360 internal units (centimeters) to inches."""
    return cm / INCH_TO_CM


LUMBER_SIZES: List[LumberSize] = [
    # 2x Framing Lumber (most common first, 2x4 default)
    LumberSize("2x4", "2x Framing", 1.5, 3.5),
    LumberSize("2x2", "2x Framing", 1.5, 1.5),
    LumberSize("2x3", "2x Framing", 1.5, 2.5),
    LumberSize("2x6", "2x Framing", 1.5, 5.5),
    LumberSize("2x8", "2x Framing", 1.5, 7.25),
    LumberSize("2x10", "2x Framing", 1.5, 9.25),
    LumberSize("2x12", "2x Framing", 1.5, 11.25),
    # 1x Boards
    LumberSize("1x2", "1x Boards", 0.75, 1.5),
    LumberSize("1x3", "1x Boards", 0.75, 2.5),
    LumberSize("1x4", "1x Boards", 0.75, 3.5),
    LumberSize("1x6", "1x Boards", 0.75, 5.5),
    LumberSize("1x8", "1x Boards", 0.75, 7.25),
    LumberSize("1x10", "1x Boards", 0.75, 9.25),
    LumberSize("1x12", "1x Boards", 0.75, 11.25),
    # 4x & 6x Timbers
    LumberSize("4x4", "Timbers", 3.5, 3.5),
    LumberSize("4x6", "Timbers", 3.5, 5.5),
    LumberSize("4x8", "Timbers", 3.5, 7.25),
    LumberSize("6x6", "Timbers", 5.5, 5.5),
    # 5/4 Decking
    LumberSize("5/4x4", "Decking", 1.0, 3.5),
    LumberSize("5/4x6", "Decking", 1.0, 5.5),
]

LUMBER_BY_LABEL: Dict[str, LumberSize] = {item.label: item for item in LUMBER_SIZES}
LUMBER_BY_NOMINAL: Dict[str, LumberSize] = {item.nominal: item for item in LUMBER_SIZES}


@dataclass(frozen=True)
class SheetThickness:
    name: str
    thickness_in: float
    max_width_in: float
    max_length_in: float
    presets: Tuple[Tuple[str, str, str], ...]
    note: str = ""

    @property
    def thickness_cm(self) -> float:
        return self.thickness_in * INCH_TO_CM

    @property
    def label(self) -> str:
        base = f'{self.name} ({_fmt_in(self.thickness_in)}")'
        return f"{base} - {self.note}" if self.note else base

    @property
    def max_size_label(self) -> str:
        return f'Max sheet: {_fmt_in(self.max_width_in)}" x {_fmt_in(self.max_length_in)}"'

    def fits_in_sheet(self, width_in: float, length_in: float) -> bool:
        """Return True if (width_in, length_in) fits within max sheet in either orientation."""
        eps = 1e-6
        normal = width_in <= self.max_width_in + eps and length_in <= self.max_length_in + eps
        rotated = length_in <= self.max_width_in + eps and width_in <= self.max_length_in + eps
        return normal or rotated


_STANDARD_4X8_PRESETS: Tuple[Tuple[str, str, str], ...] = (
    ('4\' x 8\' (48" x 96")', "48 in", "96 in"),
    ('4\' x 4\' (48" x 48")', "48 in", "48 in"),
    ('2\' x 4\' (24" x 48")', "24 in", "48 in"),
)

_BALTIC_5X5_PRESETS: Tuple[Tuple[str, str, str], ...] = (
    ('5\' x 5\' (60" x 60")', "60 in", "60 in"),
    ('30" x 60" Half Sheet', "30 in", "60 in"),
    ('24" x 48" Panel', "24 in", "48 in"),
)

_HARDBOARD_PRESETS: Tuple[Tuple[str, str, str], ...] = (
    ('4\' x 8\' (48" x 96")', "48 in", "96 in"),
    ('2\' x 4\' (24" x 48")', "24 in", "48 in"),
)

SHEET_THICKNESSES: List[SheetThickness] = [
    # Standard Plywood (PS 1 / PS 2 undersized nominal, 4x8 max)
    SheetThickness('3/4" Plywood', 23.0 / 32.0, 48.0, 96.0, _STANDARD_4X8_PRESETS, '23/32"'),
    SheetThickness('1/2" Plywood', 15.0 / 32.0, 48.0, 96.0, _STANDARD_4X8_PRESETS, '15/32"'),
    SheetThickness('5/8" Plywood', 19.0 / 32.0, 48.0, 96.0, _STANDARD_4X8_PRESETS, '19/32"'),
    SheetThickness('3/8" Plywood', 11.0 / 32.0, 48.0, 96.0, _STANDARD_4X8_PRESETS, '11/32"'),
    SheetThickness('1/4" Plywood', 0.25, 48.0, 96.0, _STANDARD_4X8_PRESETS),
    # MDF / Melamine / Hardboard (true thickness, 4x8 max)
    SheetThickness('3/4" MDF / Melamine', 0.75, 48.0, 96.0, _STANDARD_4X8_PRESETS),
    SheetThickness('1/2" MDF', 0.5, 48.0, 96.0, _STANDARD_4X8_PRESETS),
    SheetThickness('1/4" MDF', 0.25, 48.0, 96.0, _STANDARD_4X8_PRESETS),
    SheetThickness('1/8" Hardboard', 0.125, 48.0, 96.0, _HARDBOARD_PRESETS),
    # Baltic Birch (exact metric, 5x5 max)
    SheetThickness("18mm Baltic Birch", 18.0 / 25.4, 60.0, 60.0, _BALTIC_5X5_PRESETS),
    SheetThickness("12mm Baltic Birch", 12.0 / 25.4, 60.0, 60.0, _BALTIC_5X5_PRESETS),
    SheetThickness("6mm Baltic Birch", 6.0 / 25.4, 60.0, 60.0, _BALTIC_5X5_PRESETS),
]

SHEET_BY_LABEL: Dict[str, SheetThickness] = {item.label: item for item in SHEET_THICKNESSES}
SHEET_BY_NAME: Dict[str, SheetThickness] = {item.name: item for item in SHEET_THICKNESSES}


def format_component_name(nominal: str, length_cm: float) -> str:
    """Build a readable Fusion component name like '2x4 - 96 in'."""
    length_in = cm_to_inches(length_cm)
    return f"{nominal} - {length_in:g} in"


def format_sheet_component_name(
    sheet_name: str, width_cm: float, length_cm: float
) -> str:
    """Build a readable Fusion component name like '3/4\" Plywood - 48x96 in'."""
    w_in = cm_to_inches(width_cm)
    l_in = cm_to_inches(length_cm)
    return f"{sheet_name} - {w_in:g}x{l_in:g} in"
