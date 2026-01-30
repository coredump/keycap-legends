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

### Visual debugging

The `ocp_vscode` library (included as a dependency) has a standalone viewer mode. To visualize all generated shapes for debugging, replace `show` with `show_all` in `main.py`:

```python
from ocp_vscode import show_all
# ... at the end of the script:
show_all()
```

This opens a 3D viewer window showing all parts, useful for verifying legend placement and geometry.

## uv Commands Reference

```bash
uv sync              # Install/update dependencies from pyproject.toml
uv add <package>     # Add a new dependency
uv remove <package>  # Remove a dependency
uv run <script>      # Run a Python script in the virtual environment
uv lock              # Update the lock file
```

## Configuration

Edit `config.toml` to configure legends and settings. No Python knowledge required!

### Settings

```toml
[settings]
font = "Rajdhani"           # Default font for legends
primary_font_size = 8       # Main character size (mm)
secondary_font_size = 6     # Symbol size (mm)
tertiary_font_size = 5      # Third character size (mm)
legend_gap = 0.0            # Gap between primary and secondary
vertical_shift = 0.0        # Shift legend block up/down
tertiary_x_offset = -5.0    # Tertiary position (negative = left)
```

### STEP Files

```toml
[step_files.row_2]
path = "assets/1u_row_2.step"
rotation = 0  # Optional, degrees
```

### Legend Entries

```toml
[[legends.row_2]]
primary = "q"
secondary = "`"
mirror_x = false            # Optional, for reachy keys
primary_font = "Rajdhani"   # Optional override
secondary_font = "FantasqueSansM Nerd Font Propo"  # Optional override
tertiary = "1"              # Optional third character
tertiary_font = "Rajdhani"  # Optional override
```

## Using Your Own STEP Files

This project is designed to work with the STEP files in `assets/`, which are sculpted keycap shells from the "Subliminal Contradiction" keycap set.

**It should be generic enough to work with other keycap STEP files**, but:

1. The STEP file should be a solid keycap body (without stem)
2. The largest bottom face is used for stem and legend placement
3. You may need to adjust rotation in `STEP_FILES`
4. Font sizes and positioning may need tuning

**The author can't provide much support for custom STEP files** - you're on your own for debugging CAD geometry issues. Good luck!

## TODO

- [ ] Add thumb keys

## License

MIT License - see [LICENSE](LICENSE) file.
