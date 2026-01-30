# AGENTS.md

Extended context for AI assistants working on this project.

## Project Overview

This project generates 3D-printable keycaps with:
1. **Text legends** - Characters carved into the keycap top surface
2. **Kailh Choc stems** - Low-profile switch mount geometry

Input: STEP files of keycap shells (from FreeCAD)
Output: 3MF files with multi-colored parts (body, legend, stem)

## Architecture

### main.py Workflow

1. Load keycap STEP file and center at origin
2. Find the largest face (top/internal surface)
3. Create a Plane from that face for text placement
4. Build Choc stem geometry (cross rail + two cylindrical stems)
5. For each legend character:
   - Extrude 3D text into the keycap
   - Boolean subtract to create legend cavity
   - Separate body and legend as distinct parts
   - Export as 3MF with stem

### Mesher Patch (utils/mesher_patch.py)

Fixes two bugs in build123d's Mesher class:

1. **Null triangulation** - OCCT's `BRep_Tool.Triangulation_s()` can return `None` for some faces. The patch skips these instead of crashing on `NbNodes()`.

2. **Boundary holes** - Vertex merging during 3MF creation can collapse triangles, leaving holes. The patch:
   - Detects boundary edges (edges in only one triangle)
   - Traces closed loops
   - Fills with fan triangulation

## Code Patterns

### build123d Idioms

```python
# Boolean operations
result = shape1 + shape2  # Union
result = shape1 - shape2  # Subtraction

# Positioning with Pos
[Pos(x, y), Pos(x2, y2)] * shape  # Creates copies at positions

# Alignment
Box(w, h, d, align=(Align.CENTER, Align.CENTER, Align.MAX))

# Sketches and extrusion
with BuildSketch(plane) as bs:
    Text("A", font_size=8)
solid = extrude(bs.sketch, amount=4)
```

### Choc Stem Dimensions

- Cross rail: 8.9mm × 0.5mm × 0.4mm
- Stem spacing: ±2.85mm from center
- Stem body: 1.3mm × 3mm × 3.1mm
- Cutout cylinders: 3.4mm radius at ±3.9mm

## Configuration

The `LEGENDS` list in main.py controls which characters to generate:
```python
LEGENDS = ["6"]  # Currently just "6"
```

To generate multiple keycaps, add characters:
```python
LEGENDS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
```

## Common Tasks

### Add a new legend character
Edit `LEGENDS` list in main.py.

### Use a different keycap base
Change the `import_step()` path in main.py:
```python
cap = import_step("assets/your_keycap.step")
```

### Adjust text size
Modify the `font_size` parameter in the Text() call:
```python
Text(legend_text, font_size=8, ...)  # Default is 8
```

### Change mesh quality
Adjust deflection parameters in `m.add_shape()`:
- Lower values = finer mesh, larger file
- `linear_deflection`: chord height tolerance
- `angular_deflection`: angle tolerance in radians

## Known Issues

1. **Some STEP faces don't triangulate** - Handled by mesher_patch.py
2. **Vertex merging creates holes** - Handled by boundary loop filling
3. **ShapeList vs Solid** - Boolean ops can return either; main.py handles both cases

## File Formats

- **STEP** (.step): Standard CAD exchange format, used for input
- **FCStd**: FreeCAD native format (source files in assets/)
- **3MF** (.3mf): 3D printing format with multi-material support

## Environment

- Python 3.12+ required
- Uses `uv` for dependency management
- VSCode with ocp-vscode extension recommended for visualization