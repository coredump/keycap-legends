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
- Use dataclasses for structured configuration (see models.py)
- Use FontStyle.BOLD for legend text

### Common Pitfalls to Avoid
1. **Mirror timing**: Always mirror cap/stem BEFORE boolean operations, not after
2. **Plane rotation**: Use fixed `x_dir=Vector(1, 0, 0)` to prevent legend rotating with cap
3. **Legend extraction**: Use intersection (`&`) not subtraction for extracting legend solid
4. **Filtering solids**: Use `max()` by volume for hole_cap (largest), but boolean results may be ShapeList or Solid

### When Modifying Configuration
- Edit `config.toml` for legends, STEP files, and settings - no Python needed
- Edit `models.py` to add new dataclass fields
- Edit `config.py` to handle new TOML fields
- Nerd Font icons use unicode escapes like `"\uf069"` or `"\U000f0725"` in TOML

### Testing Changes
- Visual output via ocp-vscode standalone viewer or `show_all()`
- Check `results/` folder for generated 3MF files
- Meshing errors are caught and logged, script continues to next legend

## Project Overview

This project generates 3D-printable keycaps with:
1. **Text legends** - Characters carved into the keycap top surface (primary, secondary, and optional tertiary)
2. **Kailh Choc stems** - Low-profile switch mount geometry

Input: STEP files of keycap shells (from FreeCAD)
Output: 3MF files with multi-colored parts (body, legend, stem)

## Project Structure

```
keycap_legends/
├── main.py          # Entry point and processing logic
├── config.py        # TOML configuration loader
├── models.py        # Dataclasses (LegendEntry, Config, etc.)
├── config.toml      # User configuration (legends, settings)
├── fonts.py         # Utility to list available fonts
├── utils/
│   ├── mesher_patch.py  # Fixes for build123d Mesher bugs
│   └── safe_mesher.py   # SafeMesher class (alternative)
├── assets/          # STEP files for keycap bases
└── results/         # Generated 3MF output files
```

## Architecture

### Module Responsibilities

- **models.py**: Dataclasses for type-safe configuration
  - `LegendEntry` - single legend configuration
  - `StepFileConfig` - STEP file path and rotation
  - `LegendSettings` - font sizes, gaps, offsets
  - `Config` - complete configuration container

- **config.py**: Loads and parses `config.toml` into dataclasses

- **main.py**: Processing logic
  - `build_choc_stem()` - creates stem geometry
  - `build_legend_desc()` - generates description string
  - `build_filename()` - creates safe output filename
  - `main()` - entry point, orchestrates generation

### main.py Workflow

1. Load configuration from `config.toml`
2. Build Choc stem geometry once
3. For each row in legends:
   - Load STEP file and apply rotation
   - Center at origin
   - Find largest face for placement plane
4. For each legend entry:
   - Mirror cap/stem if needed (BEFORE boolean ops)
   - Create text solids
   - Boolean subtract/intersect
   - Export as 3MF

### Mesher Patch (utils/mesher_patch.py)

Fixes two bugs in build123d's Mesher class:

1. **Null triangulation** - OCCT's `BRep_Tool.Triangulation_s()` can return `None` for some faces. The patch skips these instead of crashing on `NbNodes()`.

2. **Boundary holes** - Vertex merging during 3MF creation can collapse triangles, leaving holes. The patch:
   - Detects boundary edges (edges in only one triangle)
   - Traces closed loops
   - Fills with fan triangulation

## Configuration (config.toml)

### Settings
```toml
[settings]
font = "Rajdhani"
primary_font_size = 8
secondary_font_size = 6
tertiary_font_size = 5
legend_gap = 0.0
vertical_shift = 0.0
tertiary_x_offset = -5.0
```

### STEP Files
```toml
[step_files.row_2]
path = "assets/1u_row_2.step"
rotation = 0  # Optional
```

### Legends
```toml
[[legends.row_2]]
primary = "q"
secondary = "`"
mirror_x = false
secondary_font = "FantasqueSansM Nerd Font Propo"
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

# Sketches and extrusion
with BuildSketch(plane) as bs:
    Text("A", font_size=8, font_style=FontStyle.BOLD)
solid = extrude(bs.sketch, amount=4, dir=plane.z_dir)

# Mirroring (must happen BEFORE boolean ops if legend alignment matters)
mirrored_cap = mirror(cap, Plane.YZ)
```

### Choc Stem Dimensions

- Stem spacing: ±2.85mm from center
- Stem body: 1.3mm × 3mm × 3.1mm
- Cutout cylinders: 3.4mm radius at ±3.9mm

## Common Tasks

### Add a new legend
Add entry to `config.toml`:
```toml
[[legends.row_2]]
primary = "x"
secondary = "+"
```

### Use a different keycap base
Add to `config.toml`:
```toml
[step_files.my_row]
path = "assets/my_keycap.step"
rotation = 90
```

### Adjust text size
Edit `[settings]` in `config.toml`.

### Use custom font for a character
```toml
[[legends.row_2]]
primary = "q"
secondary_font = "FantasqueSansM Nerd Font Propo"
```

## Known Issues

1. **Some STEP faces don't triangulate** - Handled by mesher_patch.py
2. **Vertex merging creates holes** - Handled by boundary loop filling
3. **ShapeList vs Solid** - Boolean ops can return either; main.py handles both cases
4. **build123d type mismatches** - Functions return Compound instead of Part; use `# type: ignore[assignment]`

## File Formats

- **STEP** (.step): Standard CAD exchange format, used for input
- **FCStd**: FreeCAD native format (source files in assets/)
- **3MF** (.3mf): 3D printing format with multi-material support, uses Unit.MM
- **TOML** (.toml): Configuration format

## Environment

- Python 3.12+ required
- Uses `uv` for dependency management
- Run with: `uv run main.py`

## Filename Mapping

Special characters are mapped to safe filenames in `FILENAME_MAP` (main.py):
```python
FILENAME_MAP = {
    "<": "less", ">": "greater", "/": "slash", ":": "colon",
    "\\": "backslash", "|": "pipe", "?": "question",
    "*": "asterisk", '"': "quote",
}
```
Output format: `results/K_{primary}_{secondary}_{row_name}.3mf`
