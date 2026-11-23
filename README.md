# TimberLine — Woodworking Add-In for Autodesk Fusion

Create standard North American dimensional lumber (`2x4`, `2x6`, `1x4`, `4x4`, `5/4x6`, etc.), sheet stock (`3/4" Plywood`, `1/2" MDF`, `18mm Baltic Birch`, etc.), and common woodworking joints directly in Autodesk Fusion.

## 1. Create Lumber / Sheet Stock (`Solid → Create → Create Lumber`)

### Dimensional Lumber (PS 20-20 Actual Sizes)
- **2x Framing:** `2x2` (1.5" × 1.5"), `2x3` (1.5" × 2.5"), `2x4` (1.5" × 3.5"), `2x6` (1.5" × 5.5"), `2x8` (1.5" × 7.25"), `2x10` (1.5" × 9.25"), `2x12` (1.5" × 11.25")
- **1x Boards:** `1x2`–`1x12` (`0.75"` thick)
- **Timbers:** `4x4`, `4x6`, `4x8`, `6x6`
- **Decking:** `5/4x4`, `5/4x6` (`1.0"` thick)

### Sheet Stock (Per-Material Max Sheet Limits)
- **Plywood (max 48" × 96"):** `3/4"` (`23/32"`), `5/8"` (`19/32"`), `1/2"` (`15/32"`), `3/8"` (`11/32"`), `1/4"` (`0.25"`)
- **MDF / Melamine / Hardboard (max 48" × 96"):** `3/4" MDF / Melamine`, `1/2" MDF`, `1/4" MDF`, `1/8" Hardboard`
- **Baltic Birch (max 60" × 60"):** `18mm`, `12mm`, `6mm`
- Automatically filters presets (`4' × 8'`, `5' × 5'`, etc.) and validates against the material's max sheet size.

## 2. Add Joinery (`Solid → Create → Add Joinery`)
- **Rabbet** — Cut a step along a selected face + edge.
- **Dado / Groove** — Cut a channel offset from a reference edge.
- **Half-Lap** — Cut an end lap joint along a selected end edge.
- **Tenon** — Cut centered shoulders on an end face to leave a rectangular tenon.
- **Mortise** — Cut a centered rectangular mortise pocket on a face.
- **Pocket Holes (15°)** — Drill 15° angled `3/8"` pocket bores + `5/32"` pilot holes along an edge.
- **Dowel Holes** — Drill evenly spaced dowel holes on an end or side face (for butt/edge joints).

## 3. Cut List & Kerf Planner (`Solid → Create → Cut List & Kerf`)
- Scans all visible lumber and sheet stock bodies in the active design.
- Packs linear cuts into standard stock lengths (`96"`, `120"`, `144"`, etc.) and sheet parts onto per-material max sheets (`48" × 96"`, `60" × 60"`), accounting for **saw blade kerf** (default `1/8"`) and **end trim allowance**.
- Displays board-by-board / sheet-by-sheet cut layouts, kerf loss, offcut/waste, and optionally exports to `.txt`.

## Installation
Run `install.ps1` in PowerShell:
```powershell
.\install.ps1
```
Then in Autodesk Fusion: **Shift+S** → **Add-Ins** tab → select **TimberLine** → **Run**.
