# Changelog

All notable changes to **TimberLine** are documented in this file.

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
