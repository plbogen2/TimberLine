# Changelog

All notable changes to **TimberLine** are documented in this file.

## [1.3.2] - 2026-11-22
### Fixed
- **Attach Board** now extrudes the new board **outward** from the selected **Source Face** (`+Z` normal) instead of sideways off the face, with **Half-Lap** and **Miter (45°)** overlapping into the existing board behind the face.

## [1.3.1] - 2026-11-22
### Changed
- **Create Lumber** and **Attach Board** now default **Create New Component** to `False`, creating each board as a named `BRepBody` directly in the active component.

## [1.3.0] - 2026-11-22
### Added
- **Attach Board** command (`Solid → Create → Attach Board`) for iterative board → joint → next-board building with **Butt (Flush)** (exact length or total outer span), **Miter (45°)**, and **Half-Lap** corner joints.
- **List Operations** command (`Solid → Create → List Operations`) displaying session TimberLine operations and Fusion's design timeline with `.txt` export.

### Removed
- Replaced rigid 4-sided **Create Frame** preset with the flexible **Attach Board** workflow.

## [1.2.0] - 2026-11-22
### Added
- **Create Frame** command (`Solid → Create → Create Frame`) to build assembled 4-sided rectangular frames (e.g., `8' × 4'` table/workbench aprons) with automatic rail length adjustments for **Butt (Long Rails Full)**, **Butt (Short Rails Full)**, **Mitered (45°)**, and **Half-Lap Corners**.

## [1.1.0] - 2026-11-22
### Added
- **Sheet Stock** support (Plywood, MDF, Hardboard, Baltic Birch) with per-material max-sheet validation and presets.
- **Add Joinery** command: Rabbet, Dado / Groove, Half-Lap, Tenon, Mortise, 15° Pocket Holes, Dowel Holes, **Reference Board** auto-sizing, and **Housing / Dado (2-Board)** boolean cut.
- **Cut List & Kerf** planner with 1D/2D blade-kerf packing and `.txt` export.
- **Autodesk App Store** `.bundle` packaging (`PackageContents.xml`, `build_bundle.ps1`).
- Automated `tests/` suite with >=95% per-module statement coverage.

### Fixed
- `TimberLine.manifest` schema (`autodeskProduct: "Fusion360"`, `type: "addin"`).
- Single-component **Part Design** fallback when `addNewComponent` is restricted.
- 15° pocket hole drill angle (`75°` perpendicular plane) and outward start-plane offset.

## [1.0.0] - 2026-11-22
### Added
- Initial release with **Create Lumber** for North American nominal dimensional lumber (`1x`, `2x`, `4x`, `6x`, `5/4` decking).
