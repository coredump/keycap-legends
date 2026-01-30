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

from config import load_config
from models import LegendEntry
from utils.mesher_patch import apply_mesher_triangulation_none_guard

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


def build_choc_stem() -> Part:
    """Build the Kailh Choc stem geometry."""
    # Cross is used for alignment reference only, not included in final stem
    stem: Part = Box(1.3, 3, 3.1, align=(Align.CENTER, Align.CENTER, Align.MAX)) - [
        Pos(3.9, 0),
        Pos(-3.9, 0),
    ] * Cylinder(3.4, 3.1, align=(Align.CENTER, Align.CENTER, Align.MAX))
    stem = fillet(stem.edges().group_by(Axis.Z)[:-1], 0.15)  # type: ignore[arg-type]
    return Pos(2.85, 0) * stem + Pos(-2.85, 0) * stem  # type: ignore[return-value]


def build_legend_desc(entry: LegendEntry) -> str | None:
    """Build a description string for the legend entry."""
    if entry.primary and entry.secondary and entry.tertiary:
        return f"{entry.primary}+{entry.secondary}+{entry.tertiary}"
    elif entry.primary and entry.secondary:
        return f"{entry.primary}+{entry.secondary}"
    elif entry.primary and entry.tertiary:
        return f"{entry.primary}+{entry.tertiary}"
    elif entry.primary:
        return entry.primary
    elif entry.secondary:
        return entry.secondary
    return None


def build_filename(entry: LegendEntry, row_name: str) -> str:
    """Build a safe filename for the keycap."""
    parts: list[str] = []
    if entry.primary:
        parts.append(FILENAME_MAP.get(entry.primary, entry.primary))
    if entry.secondary:
        parts.append(FILENAME_MAP.get(entry.secondary, entry.secondary))
    if entry.tertiary:
        parts.append(FILENAME_MAP.get(entry.tertiary, entry.tertiary))
    return f"results/K_{'_'.join(parts)}_{row_name}.3mf"


def main() -> None:
    """Main entry point for keycap generation."""
    apply_mesher_triangulation_none_guard()
    set_defaults(reset_camera=Camera.CENTER, helper_scale=1, transparent=False)

    # Load configuration
    cfg = load_config()
    settings = cfg.settings

    # Build stem geometry once
    choc_stem_base: Part = build_choc_stem()

    for row_name, legend_entries in cfg.legends.items():
        print(f"Processing {row_name}...")

        # Get STEP file config
        step_cfg = cfg.step_files[row_name]
        cap: Part = import_step(step_cfg.path)  # type: ignore[assignment]
        if step_cfg.rotation != 0:
            cap = Rot(0, 0, step_cfg.rotation) * cap
        bbox = cap.bounding_box()
        cap = Pos(-bbox.center().X, -bbox.center().Y, -bbox.min.Z) * cap

        internal_face = max(cap.faces(), key=lambda f: f.area)
        n: Vector = internal_face.normal_at()
        # Use fixed x_dir so legend/stem orientation doesn't change with cap rotation
        pln: Plane = Plane(
            origin=Vector(0, 0, internal_face.center().Z),
            z_dir=-n,
            x_dir=Vector(1, 0, 0),
        )

        choc_stem: Part = pln.location * choc_stem_base
        choc_stem.color = Color("gray")
        choc_stem.label = "stem"

        for entry in legend_entries:
            legend_desc = build_legend_desc(entry)
            if not legend_desc:
                print("  Skipping: no legend specified")
                continue

            print(
                f"  Creating keycap with legend: {legend_desc}"
                + (" (mirrored)" if entry.mirror_x else "")
            )

            # Resolve fonts with fallbacks
            primary_font = entry.primary_font or settings.font
            secondary_font = entry.secondary_font or primary_font
            tertiary_font = entry.tertiary_font or settings.font

            print("    Mirroring cap/stem...")
            # Mirror cap and stem BEFORE boolean operations so legend aligns correctly
            working_cap: Part
            working_stem: Part
            if entry.mirror_x:
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
            if entry.primary and entry.secondary:
                # Both legends - offset and position as a group
                total_height = (
                    settings.primary_font_size
                    + settings.legend_gap
                    + settings.secondary_font_size
                )
                primary_offset = (
                    -total_height / 2
                    + settings.primary_font_size / 2
                    + settings.vertical_shift
                )
                secondary_offset = (
                    total_height / 2
                    - settings.secondary_font_size / 2
                    + settings.vertical_shift
                )

                print("    Creating primary text...")
                primary_pln = Plane(
                    origin=text_pln.origin + text_pln.y_dir * primary_offset,
                    z_dir=text_pln.z_dir,
                    x_dir=text_pln.x_dir,
                )
                with BuildSketch(primary_pln) as bs:
                    Text(
                        entry.primary,
                        font_size=settings.primary_font_size,
                        font=primary_font,
                        font_style=FontStyle.BOLD,
                        align=(Align.CENTER, Align.CENTER),
                    )
                print("    Extruding primary text...")
                text_solid = extrude(
                    bs.sketch, amount=4, dir=text_pln.z_dir, both=False
                )  # type: ignore[assignment]

                print("    Creating secondary text...")
                secondary_pln = Plane(
                    origin=text_pln.origin + text_pln.y_dir * secondary_offset,
                    z_dir=text_pln.z_dir,
                    x_dir=text_pln.x_dir,
                )
                with BuildSketch(secondary_pln) as bs:
                    Text(
                        entry.secondary,
                        font_size=settings.secondary_font_size,
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

                # Add tertiary legend if specified
                if entry.tertiary:
                    print("    Creating tertiary text...")
                    tertiary_pln = Plane(
                        origin=text_pln.origin
                        + text_pln.x_dir * settings.tertiary_x_offset,
                        z_dir=text_pln.z_dir,
                        x_dir=text_pln.x_dir,
                    )
                    with BuildSketch(tertiary_pln) as bs:
                        Text(
                            entry.tertiary,
                            font_size=settings.tertiary_font_size,
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

            elif entry.primary:
                # Only primary - centered on keycap
                print("    Creating primary text (centered)...")
                with BuildSketch(text_pln) as bs:
                    Text(
                        entry.primary,
                        font_size=settings.primary_font_size,
                        font=primary_font,
                        align=(Align.CENTER, Align.CENTER),
                    )
                print("    Extruding primary text...")
                text_solid = extrude(
                    bs.sketch, amount=4, dir=text_pln.z_dir, both=False
                )  # type: ignore[assignment]

            elif entry.secondary:
                # Only secondary - centered on keycap
                print("    Creating secondary text (centered)...")
                with BuildSketch(text_pln) as bs:
                    Text(
                        entry.secondary,
                        font_size=settings.secondary_font_size,
                        font=secondary_font,
                        align=(Align.CENTER, Align.CENTER),
                    )
                print("    Extruding secondary text...")
                text_solid = extrude(
                    bs.sketch, amount=4, dir=text_pln.z_dir, both=False
                )  # type: ignore[assignment]

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
                filename = build_filename(entry, row_name)
                m.write(filename)
            except RuntimeError as e:
                print(f"    ERROR: Failed to create mesh for '{legend_desc}': {e}")


if __name__ == "__main__":
    main()
