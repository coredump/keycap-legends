# Keycap Legends

Generate 3D-printable keycaps with text legends and Kailh Choc stems.

> **Note:** This project has been vibe coded with [Claude](https://claude.ai) (Anthropic's AI assistant). The code works, but don't expect enterprise-grade polish.

## What It Does

Takes STEP files of keycap shells (from FreeCAD) and adds:
- **Text legends** - Characters carved into the keycap top surface (supports primary, secondary, and tertiary legends)
- **Kailh Choc stems** - Low-profile switch mount geometry

Outputs 3MF files with multi-colored parts (body, legend, stem) ready for multi-material 3D printing.

## Requirements

- Python 3.12+
- [mise](https://mise.jdx.dev/) (optional, for tool management)
- VS Code with [OCP CAD Viewer](https://marketplace.visualstudio.com/items?itemName=bernhard-42.ocp-cad-viewer) extension (recommended)

## Setup

### Using mise (recommended)

```bash
# Install mise if you don't have it
curl https://mise.run | sh

# Install project tools (uv, watchexec)
mise install

# Create virtual environment and install dependencies
uv sync
```

### Manual setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync
```

## Usage

### Generate keycaps

```bash
uv run main.py
```

Output files are saved to `results/` as 3MF files.

### List available fonts

```bash
uv run fonts.py
```

This lists all fonts available to build123d for legend text. Useful for finding Nerd Fonts or other installed fonts.

### Watch for changes (development)

```bash
watchexec -e py -- uv run main.py
```

## uv Commands Reference

```bash
uv sync              # Install/update dependencies from pyproject.toml
uv add <package>     # Add a new dependency
uv remove <package>  # Remove a dependency
uv run <script>      # Run a Python script in the virtual environment
uv lock              # Update the lock file
```

## Configuration

Edit `main.py` to configure:

- `font_name` - Default font for legends
- `PRIMARY_FONT_SIZE`, `SECONDARY_FONT_SIZE`, `TERTIARY_FONT_SIZE` - Font sizes in mm
- `LEGEND_GAP` - Gap between primary and secondary legends
- `STEP_FILES` - Map of row names to STEP file paths and rotation
- `LEGENDS` - Map of row names to legend tuples

### Legend Tuple Format

```python
(primary, secondary, mirror_x, [primary_font], [secondary_font], [tertiary], [tertiary_font])
```

- `primary` - Main character (bottom/center), or `None`
- `secondary` - Symbol character (top/center), or `None`
- `mirror_x` - `True` to mirror the keycap on X axis (for reachy keys)
- `primary_font` - Optional font override for primary
- `secondary_font` - Optional font override for secondary
- `tertiary` - Optional third character (left side)
- `tertiary_font` - Optional font override for tertiary

## Using Your Own STEP Files

This project is designed to work with the STEP files in `assets/`, which are sculpted keycap shells from the "Subliminal Contradiction" keycap set.

**It should be generic enough to work with other keycap STEP files**, but:

1. The STEP file should be a hollow keycap shell (not solid)
2. The largest internal face is used for legend placement
3. You may need to adjust rotation in `STEP_FILES`
4. Font sizes and positioning may need tuning

**The author can't provide much support for custom STEP files** - you're on your own for debugging CAD geometry issues. Good luck!

## TODO

- [ ] Add thumb keys

## License

MIT License - see [LICENSE](LICENSE) file.
