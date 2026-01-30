# AGENTS.md

Extended context for AI assistants working on this project.

## Claude Agent Guidelines

### Session Context
- This is a build123d CAD project - read this file fully before making changes
- The mesher_patch.py fixes critical bugs; don't remove or modify unless necessary
- Always run `uv run main.py` to test changes (user will confirm when to run)

### Code Style Preferences
- Use type annotations (Python 3.12 supports `str | None` and `list[str]` natively)
- Add `# type: ignore[assignment]` for build123d API mismatches (returns Compound, not Part)
- Keep configuration variables at top of main.py with type hints
- Use FontStyle.BOLD for legend text

### Common Pitfalls to Avoid
1. **Mirror timing**: Always mirror cap/stem BEFORE boolean operations, not after
2. **Plane rotation**: Use fixed `x_dir=Vector(1, 0, 0)` to prevent legend rotating with cap
3. **Legend extraction**: Use intersection (`&`) not subtraction for extracting legend solid
4. **Filtering solids**: Use `max()` by volume for hole_cap (largest), but boolean results may be ShapeList or Solid

### When Modifying Legends
- Tuple format: `(primary, secondary, mirror_x, [primary_font], [secondary_font], [tertiary], [tertiary_font])`
- Use `None` for missing primary/secondary to center the remaining legend
- Special characters need FILENAME_MAP entries for safe filenames
- Nerd Font icons use unicode escapes like `"\uf069"` or `"\U000f0725"`

### Testing Changes
- Visual output appears in VS Code via ocp-vscode extension
- Check `results/` folder for generated 3MF files
- Meshing errors are caught and logged, script continues to next legend

## Project Overview

This project generates 3D-printable keycaps with:
1. **Text legends** - Characters carved into the keycap top surface (primary, secondary, and optional tertiary)
2. **Kailh Choc stems** - Low-profile switch mount geometry

Input: STEP files of keycap shells (from FreeCAD)
Output: 3MF files with multi-colored parts (body, legend, stem)

## Architecture

### main.py Workflow

1. Load keycap STEP file and apply optional rotation
2. Center at origin (X/Y from bounding box, Z from internal face)
3. Find the largest face (internal surface) for text placement plane
4. Create a Plane with fixed X direction (prevents legend rotation with cap)
5. Build Choc stem geometry (two cylindrical stems at ±2.85mm)
6. For each legend entry:
   - Mirror cap/stem if mirror_x is True (BEFORE boolean ops)
   - Create text solids (primary, secondary, optional tertiary)
   - Boolean subtract from cap to create legend cavity
   - Boolean intersect to extract legend piece
   - Export as 3MF with stem

### Mesher Patch (utils/mesher_patch.py)

Fixes two bugs in build123d's Mesher class:

1. **Null triangulation** - OCCT's `BRep_Tool.Triangulation_s()` can return `None` for some faces. The patch skips these instead of crashing on `NbNodes()`.

2. **Boundary holes** - Vertex merging during 3MF creation can collapse triangles, leaving holes. The patch:
   - Detects boundary edges (edges in only one triangle)
   - Traces closed loops
   - Fills with fan triangulation

## Configuration

### Legend Font Sizes
```python
PRIMARY_FONT_SIZE: int = 8      # Main character at bottom
SECONDARY_FONT_SIZE: int = 6    # Symbol at top
TERTIARY_FONT_SIZE: int = 5     # Optional left-side character
```

### Legend Positioning
```python
LEGEND_GAP: float = 0.0              # mm between primary and secondary
LEGEND_VERTICAL_SHIFT: float = 0.0   # mm to shift legend block upward
TERTIARY_X_OFFSET: float = -5.0      # mm to shift tertiary left
```

### STEP Files
```python
# (path, rotation_degrees) - rotation around Z axis before processing
STEP_FILES: dict[str, tuple[str, int]] = {
    "row_2": ("assets/1u_row_2.step", 0),
    "row_2_reachy": ("assets/1u_row_2_left_reachy.step", 0),
    "row_3": ("assets/1u_row_3.step", 0),
    "row_3_dots": ("assets/1u_row_3_dots.step", 0),
    "row_3_reachy": ("assets/1u_row_3_reachy.step", 0),
    "row_4": ("assets/1u_row_4.step", 0),
    "row_4_reachy": ("assets/1u_row_4_reachy.step", 0),
}
```

### Legends Format
```python
# (primary, secondary, mirror_x, [primary_font], [secondary_font], [tertiary], [tertiary_font])
# - primary: main legend at bottom/center (or None)
# - secondary: legend at top/center (or None)
# - mirror_x: True mirrors the base cap on X axis (for reachy keys)
# - primary_font (optional): font for primary, defaults to font_name
# - secondary_font (optional): font for secondary, defaults to primary_font
# - tertiary (optional): legend at left side
# - tertiary_font (optional): font for tertiary, defaults to font_name

LEGENDS: dict[str, list[tuple]] = {
    "row_2": [
        ("q", "`", False, font_name, "FantasqueSansM Nerd Font Propo"),
        ("u", "{", False),  # Uses default font
        # ...
    ],
}
```

## Code Patterns

### build123d Idioms

```python
# Boolean operations
result = shape1 + shape2  # Union
result = shape1 - shape2  # Subtraction
result = shape1 & shape2  # Intersection

# Positioning with Pos
[Pos(x, y), Pos(x2, y2)] * shape  # Creates copies at positions

# Alignment
Box(w, h, d, align=(Align.CENTER, Align.CENTER, Align.MAX))

# Sketches and extrusion
with BuildSketch(plane) as bs:
    Text("A", font_size=8, font_style=FontStyle.BOLD)
solid = extrude(bs.sketch, amount=4, dir=plane.z_dir)

# Mirroring (must happen BEFORE boolean ops if legend alignment matters)
mirrored_cap = mirror(cap, Plane.YZ)
```

### Type Annotations

The code uses type annotations with `# type: ignore` comments for build123d API quirks:
```python
cap: Part = import_step(path)  # type: ignore[assignment]  # Returns Compound
working_cap = mirror(cap, Plane.YZ)  # type: ignore[assignment]
```

### Choc Stem Dimensions

- Stem spacing: ±2.85mm from center
- Stem body: 1.3mm × 3mm × 3.1mm
- Cutout cylinders: 3.4mm radius at ±3.9mm
- Cross rail (for alignment only, not in final): 8.9mm × 0.5mm × 0.4mm

## Common Tasks

### Add a new legend character
Edit the appropriate row in the `LEGENDS` dict in main.py.

### Use a different keycap base
Add entry to `STEP_FILES` dict and corresponding `LEGENDS` entry.

### Adjust text size
Modify `PRIMARY_FONT_SIZE`, `SECONDARY_FONT_SIZE`, or `TERTIARY_FONT_SIZE`.

### Use custom font for a character
Add font parameters to the legend tuple:
```python
("q", "`", False, "Rajdhani", "FantasqueSansM Nerd Font Propo")
```

### Change mesh quality
Adjust deflection parameters in `m.add_shape()`:
- Lower values = finer mesh, larger file
- `linear_deflection`: chord height tolerance
- `angular_deflection`: angle tolerance in radians
- Legend uses finer settings (0.01, 0.05) than body/stem (0.06, 0.3)

## Known Issues

1. **Some STEP faces don't triangulate** - Handled by mesher_patch.py
2. **Vertex merging creates holes** - Handled by boundary loop filling
3. **ShapeList vs Solid** - Boolean ops can return either; main.py handles both cases
4. **build123d type mismatches** - Functions return Compound instead of Part; use `# type: ignore[assignment]`

## File Formats

- **STEP** (.step): Standard CAD exchange format, used for input
- **FCStd**: FreeCAD native format (source files in assets/)
- **3MF** (.3mf): 3D printing format with multi-material support, uses Unit.MM

## Environment

- Python 3.12+ required
- Uses `uv` for dependency management
- VSCode with ocp-vscode extension recommended for visualization
- Run with: `uv run main.py`

## Filename Mapping

Special characters are mapped to safe filenames:
```python
FILENAME_MAP = {
    "<": "less", ">": "greater", "/": "slash", ":": "colon",
    "\\": "backslash", "|": "pipe", "?": "question",
    "*": "asterisk", '"': "quote",
}
```
Output format: `results/K_{primary}_{secondary}_{row_name}.3mf`
