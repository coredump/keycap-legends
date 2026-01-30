# SPDX-License-Identifier: MIT

from build123d import (
    Align,
    Axis,
    Box,
    BuildSketch,
    Color,
    Cylinder,
    FontStyle,
    Mesher,
    Part,
    Plane,
    Pos,
    Rot,
    ShapeList,
    Solid,
    Text,
    Unit,
    Vector,
    extrude,
    fillet,
    import_step,
    mirror,
)
from ocp_vscode import Camera, set_defaults, show

from utils.mesher_patch import apply_mesher_triangulation_none_guard

apply_mesher_triangulation_none_guard()

set_defaults(reset_camera=Camera.CENTER, helper_scale=1, transparent=False)

font_name: str = "Rajdhani"

# Legend configuration
PRIMARY_FONT_SIZE: int = 8
SECONDARY_FONT_SIZE: int = 6
TERTIARY_FONT_SIZE: int = 5
LEGEND_GAP: float = 0.0  # mm gap between top of primary and bottom of secondary
LEGEND_VERTICAL_SHIFT: float = 0.0  # mm to shift the whole legend block upward
TERTIARY_X_OFFSET: float = -5.0  # mm to shift tertiary legend to the left

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

# (primary, secondary, mirror_x, [primary_font], [secondary_font], [tertiary], [tertiary_font])
# - primary: main legend at bottom/center
# - secondary: legend at top/center (or None)
# - mirror_x: True mirrors the base cap on X axis
# - primary_font (optional): font for primary, defaults to font_name
# - secondary_font (optional): font for secondary, defaults to primary_font
# - tertiary (optional): legend at left side, between primary and secondary
# - tertiary_font (optional): font for tertiary, defaults to font_name
LegendEntry = tuple[str | None, str | None, bool, ...]  # variable length tuple
LEGENDS: dict[str, list[tuple]] = {
    "row_2": [
        ("q", "`", False, font_name, "FantasqueSansM Nerd Font Propo"),
        ("w", "\U000f097c", False, font_name, "FantasqueSansM Nerd Font Propo"),
        ("e", "\uedfb", False, font_name, "FantasqueSansM Nerd Font Propo"),
        ("r", "\ueacc", False, font_name, "FantasqueSansM Nerd Font Propo"),
        ("u", "{", False),
        ("i", "}", False),
        ("o", "$", False),
        ("p", "\\", False),
    ],
    "row_2_reachy": [("t", "|", False), ("y", "^", True)],
    "row_3": [
        ("a", "!", False),
        ("s", "\uf069", False, font_name, "FantasqueSansM Nerd Font Propo"),
        ("d", "/", False),
        ("k", ")", False),
        ("l", "_", False),
        (";", "'", False),
    ],
    "row_3_dots": [("f", "=", False), ("j", "(", False)],
    "row_3_reachy": [("g", "&", False), ("h", "#", True)],
    "row_4": [
        ("z", "\U000f0725", False, font_name, "FantasqueSansM Nerd Font Propo"),
        ("x", "+", False),
        ("c", "[", False),
        ("v", "]", False),
        ("m", ":", False),
        (",", None, False),
        (".", None, False),
        ("/", None, False),
    ],
    "row_4_reachy": [
        ("b", "\uf295", False, font_name, "FantasqueSansM Nerd Font Propo"),
        (
            "n",
            "\uf1fa",
            True,
            font_name,
            "FantasqueSansM Nerd Font Propo",
        ),
    ],
}

# Characters that need safe filenames
FILENAME_MAP: dict[str, str] = {
    "<": "less",
    ">": "greater",
    "/": "slash",
    ":": "colon",
    "\\": "backslash",
    "|": "pipe",
    "?": "question",
    "*": "asterisk",
    '"': "quote",
}

# choc stem base geometry (will be positioned per cap)
cross: Part = Box(8.9, 0.5, 0.4, align=(Align.CENTER, Align.CENTER, Align.MAX)) + [
    Pos(0, 0),
    Pos(-8.9 / 2 + 0.25, 0),
    Pos(8.9 / 2 - 0.25),
] * Box(0.5, 3.5, 0.4, align=(Align.CENTER, Align.CENTER, Align.MAX))
stem: Part = Box(1.3, 3, 3.1, align=(Align.CENTER, Align.CENTER, Align.MAX)) - [
    Pos(3.9, 0),
    Pos(-3.9, 0),
] * Cylinder(3.4, 3.1, align=(Align.CENTER, Align.CENTER, Align.MAX))
stem = fillet(stem.edges().group_by(Axis.Z)[:-1], 0.15)  # type: ignore[arg-type]
# cross is used for alignment reference only, not included in final stem
choc_stem_base: Part = Pos(2.85, 0) * stem + Pos(-2.85, 0) * stem

for row_name, primary_legends in LEGENDS.items():
    print(f"Processing {row_name}...")

    step_path: str
    rotation_deg: int
    step_path, rotation_deg = STEP_FILES[row_name]
    cap: Part = import_step(step_path)  # type: ignore[assignment]
    if rotation_deg != 0:
        cap = Rot(0, 0, rotation_deg) * cap
    bbox = cap.bounding_box()
    cap = Pos(-bbox.center().X, -bbox.center().Y, -bbox.min.Z) * cap

    internal_face = max(cap.faces(), key=lambda f: f.area)
    n: Vector = internal_face.normal_at()
    # Use fixed x_dir so legend/stem orientation doesn't change with cap rotation
    pln: Plane = Plane(
        origin=Vector(0, 0, internal_face.center().Z), z_dir=-n, x_dir=Vector(1, 0, 0)
    )

    choc_stem: Part = pln.location * choc_stem_base
    choc_stem.color = Color("gray")
    choc_stem.label = "stem"

    for legend_entry in primary_legends:
        # Unpack with optional font and tertiary parameters
        primary_legend: str | None = legend_entry[0]
        secondary_legend: str | None = legend_entry[1]
        mirror_x: bool = legend_entry[2]
        primary_font: str = legend_entry[3] if len(legend_entry) > 3 else font_name
        secondary_font: str = legend_entry[4] if len(legend_entry) > 4 else primary_font
        tertiary_legend: str | None = legend_entry[5] if len(legend_entry) > 5 else None
        tertiary_font: str = legend_entry[6] if len(legend_entry) > 6 else font_name

        if primary_legend and secondary_legend and tertiary_legend:
            legend_desc = f"{primary_legend}+{secondary_legend}+{tertiary_legend}"
        elif primary_legend and secondary_legend:
            legend_desc = f"{primary_legend}+{secondary_legend}"
        elif primary_legend and tertiary_legend:
            legend_desc = f"{primary_legend}+{tertiary_legend}"
        elif primary_legend:
            legend_desc = primary_legend
        elif secondary_legend:
            legend_desc = secondary_legend
        else:
            print("  Skipping: no legend specified")
            continue
        print(
            f"  Creating keycap with legend: {legend_desc}"
            + (" (mirrored)" if mirror_x else "")
        )

        print("    Mirroring cap/stem...")
        # Mirror cap and stem BEFORE boolean operations so legend aligns correctly
        working_cap: Part
        working_stem: Part
        if mirror_x:
            working_cap = mirror(cap, Plane.YZ)  # type: ignore[assignment]
            working_stem = mirror(choc_stem, Plane.YZ)  # type: ignore[assignment]
        else:
            working_cap = cap
            working_stem = choc_stem
        working_stem.color = Color("gray")
        working_stem.label = "stem"

        text_pln: Plane = Plane(
            origin=pln.origin - n * 0.4, z_dir=pln.z_dir, x_dir=pln.x_dir
        )

        text_solid: Part | None = None

        # Handle different legend configurations
        if primary_legend and secondary_legend:
            # Both legends - offset and position as a group
            total_height = PRIMARY_FONT_SIZE + LEGEND_GAP + SECONDARY_FONT_SIZE
            primary_offset = (
                -total_height / 2 + PRIMARY_FONT_SIZE / 2 + LEGEND_VERTICAL_SHIFT
            )
            secondary_offset = (
                total_height / 2 - SECONDARY_FONT_SIZE / 2 + LEGEND_VERTICAL_SHIFT
            )

            print("    Creating primary text...")
            primary_pln = Plane(
                origin=text_pln.origin + text_pln.y_dir * primary_offset,
                z_dir=text_pln.z_dir,
                x_dir=text_pln.x_dir,
            )
            with BuildSketch(primary_pln) as bs:
                Text(
                    primary_legend,
                    font_size=PRIMARY_FONT_SIZE,
                    font=primary_font,
                    font_style=FontStyle.BOLD,
                    align=(Align.CENTER, Align.CENTER),
                )
            print("    Extruding primary text...")
            text_solid = extrude(bs.sketch, amount=4, dir=text_pln.z_dir, both=False)  # type: ignore[assignment]

            print("    Creating secondary text...")
            secondary_pln = Plane(
                origin=text_pln.origin + text_pln.y_dir * secondary_offset,
                z_dir=text_pln.z_dir,
                x_dir=text_pln.x_dir,
            )
            with BuildSketch(secondary_pln) as bs:
                Text(
                    secondary_legend,
                    font_size=SECONDARY_FONT_SIZE,
                    font=secondary_font,
                    font_style=FontStyle.BOLD,
                    align=(Align.CENTER, Align.CENTER),
                )
            print("    Extruding secondary text...")
            secondary_solid = extrude(
                bs.sketch, amount=4, dir=text_pln.z_dir, both=False
            )
            print("    Combining text solids...")
            text_solid = text_solid + secondary_solid  # type: ignore[assignment]

            # Add tertiary legend if specified (positioned to the left, between primary and secondary)
            if tertiary_legend:
                print("    Creating tertiary text...")
                tertiary_pln = Plane(
                    origin=text_pln.origin + text_pln.x_dir * TERTIARY_X_OFFSET,
                    z_dir=text_pln.z_dir,
                    x_dir=text_pln.x_dir,
                )
                with BuildSketch(tertiary_pln) as bs:
                    Text(
                        tertiary_legend,
                        font_size=TERTIARY_FONT_SIZE,
                        font=tertiary_font,
                        font_style=FontStyle.BOLD,
                        align=(Align.CENTER, Align.CENTER),
                    )
                print("    Extruding tertiary text...")
                tertiary_solid = extrude(
                    bs.sketch, amount=6, dir=text_pln.z_dir, both=False
                )
                print("    Combining tertiary text...")
                text_solid = text_solid + tertiary_solid  # type: ignore[assignment]

        elif primary_legend:
            # Only primary - centered on keycap
            print("    Creating primary text (centered)...")
            with BuildSketch(text_pln) as bs:
                Text(
                    primary_legend,
                    font_size=PRIMARY_FONT_SIZE,
                    font=primary_font,
                    align=(Align.CENTER, Align.CENTER),
                )
            print("    Extruding primary text...")
            text_solid = extrude(bs.sketch, amount=4, dir=text_pln.z_dir, both=False)  # type: ignore[assignment]

        elif secondary_legend:
            # Only secondary - centered on keycap
            print("    Creating secondary text (centered)...")
            with BuildSketch(text_pln) as bs:
                Text(
                    secondary_legend,
                    font_size=SECONDARY_FONT_SIZE,
                    font=secondary_font,
                    align=(Align.CENTER, Align.CENTER),
                )
            print("    Extruding secondary text...")
            text_solid = extrude(bs.sketch, amount=4, dir=text_pln.z_dir, both=False)  # type: ignore[assignment]

        print("    Boolean subtract (hole_cap)...")
        hole_cap: Part | Solid = working_cap - text_solid  # type: ignore[operator]
        if isinstance(hole_cap, ShapeList):
            hole_cap = max(hole_cap, key=lambda s: s.volume)
        else:
            solids = list(hole_cap.solids())
            if len(solids) > 1:
                hole_cap = max(solids, key=lambda s: s.volume)

        print("    Boolean intersect (legend)...")
        # Use intersection instead of subtraction - much faster
        legend: Part | Solid = working_cap & text_solid  # type: ignore[operator]
        print("    Legend created")

        hole_cap.color = Color("gray")
        hole_cap.label = "cap body"
        legend.color = Color("black")
        legend.label = "legend"

        try:
            show([hole_cap, legend, working_stem])
            print("    Meshing shapes...")
            m: Mesher = Mesher(unit=Unit.MM)
            m.add_shape(hole_cap, linear_deflection=0.06, angular_deflection=0.3)
            print("    Meshed hole_cap")
            m.add_shape(legend, linear_deflection=0.01, angular_deflection=0.05)
            print("    Meshed legend")
            m.add_shape(working_stem, linear_deflection=0.06, angular_deflection=0.3)
            print("    Meshed stem")
            # Build filename from legends
            parts: list[str] = []
            if primary_legend:
                parts.append(FILENAME_MAP.get(primary_legend, primary_legend))
            if secondary_legend:
                parts.append(FILENAME_MAP.get(secondary_legend, secondary_legend))
            if tertiary_legend:
                parts.append(FILENAME_MAP.get(tertiary_legend, tertiary_legend))
            filename: str = f"results/K_{'_'.join(parts)}_{row_name}.3mf"
            m.write(filename)
        except RuntimeError as e:
            print(f"    ERROR: Failed to create mesh for '{legend_desc}': {e}")
