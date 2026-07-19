# SPDX-License-Identifier: MIT

import math
from pathlib import Path

from build123d import (
    Align,
    Axis,
    BoundBox,
    Box,
    BuildSketch,
    Color,
    Compound,
    Cylinder,
    Kind,
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
    offset,
)
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from OCP.TopTools import TopTools_ListOfShape
from ocp_vscode import Camera, set_defaults, show

from config import load_config
from models import LegendEntry
from utils.bambu_project import bambuify_3mf
from utils.mesher_patch import apply_mesher_triangulation_none_guard
from utils.stl_to_step import convert_stl_to_step

# =============================================================================
# DEBUG SETTINGS - Set to filter which rows to process
# =============================================================================
# Set to None or empty list to process all rows
# Set to a list of row names to process only those rows
# Examples:
#   ONLY_ROWS = None                           # Process all rows
#   ONLY_ROWS = ["row_2"]                      # Process only row_2
# ONLY_ROWS = ["thumb_mid", "thumb_corners"]  # Process only thumb keys
ONLY_ROWS: list[str] | None = None
# Filter by entry name/primary for fine-grained sampling (e.g. ["Q", "O"])
ONLY_KEYS: list[str] | None = None
# =============================================================================

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


def fuzzy_boolean(a: Part, b: Part, cut: bool) -> Part | None:
    """Boolean with fuzzy tolerance - fallback when exact booleans fail.

    OCCT's exact booleans can silently return nothing when tool faces are
    tangent to the target (e.g. arc-joined offset text). A small fuzzy value
    merges the near-coincident geometry and lets the operation succeed.
    """
    op = BRepAlgoAPI_Cut() if cut else BRepAlgoAPI_Common()
    args = TopTools_ListOfShape()
    args.Append(a.wrapped)
    tools = TopTools_ListOfShape()
    tools.Append(b.wrapped)
    op.SetArguments(args)
    op.SetTools(tools)
    op.SetFuzzyValue(1e-5)
    op.Build()
    if not op.IsDone():
        return None
    return Compound(op.Shape())  # type: ignore[return-value]


def build_choc_stem() -> Part:
    """Build the Kailh Choc stem geometry."""
    # Cross is used for alignment reference only, not included in the final stem
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
    if entry.name:
        parts.append(entry.name)
    elif entry.primary:
        parts.append(FILENAME_MAP.get(entry.primary, entry.primary))
    if entry.secondary:
        parts.append(FILENAME_MAP.get(entry.secondary, entry.secondary))
    if entry.tertiary:
        parts.append(FILENAME_MAP.get(entry.tertiary, entry.tertiary))
    return f"results/K_{'_'.join(parts)}_{row_name}.3mf"


def find_legend_plane_z(
    cap: Part, bbox: BoundBox, footprint: BoundBox | None = None
) -> float:
    """Find the Z coordinate for legend placement.

    Returns the minimum Z among top-surface vertices (top 60% by height)
    within the legend footprint - by default a 3mm radius around center,
    or the actual text extent when `footprint` is given. On slanted caps
    the surface keeps dropping toward the edges, so using the real
    footprint prevents glyph corners from ending up below the text solid.
    """
    cap_top_z = bbox.max.Z
    cap_bottom_z = bbox.min.Z
    cap_height = cap_top_z - cap_bottom_z

    # Only consider the upper portion (top 60%)
    z_threshold = cap_bottom_z + cap_height * 0.4

    if footprint is not None:
        # Clamp away from the side walls so wall vertices don't drag z down
        margin = 0.3
        wall_inset = 1.5
        x_min = max(footprint.min.X - margin, bbox.min.X + wall_inset)
        x_max = min(footprint.max.X + margin, bbox.max.X - wall_inset)
        y_min = max(footprint.min.Y - margin, bbox.min.Y + wall_inset)
        y_max = min(footprint.max.Y + margin, bbox.max.Y - wall_inset)
    else:
        x_min = y_min = -3.0
        x_max = y_max = 3.0

    candidate_z_values: list[float] = []
    for vertex in cap.vertices():
        v = vertex.center()
        if x_min < v.X < x_max and y_min < v.Y < y_max and v.Z > z_threshold:
            candidate_z_values.append(v.Z)

    if candidate_z_values:
        return min(candidate_z_values)

    # Fallback
    return cap_top_z


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
        # Skip rows not in the ONLY_ROWS filter (if set)
        if ONLY_ROWS and row_name not in ONLY_ROWS:
            print(f"Skipping {row_name} (not in ONLY_ROWS)")
            continue

        print(f"Processing {row_name}...")

        # Get STEP file config
        step_cfg = cfg.step_files[row_name]
        if not Path(step_cfg.path).exists():
            if step_cfg.stl and Path(step_cfg.stl).exists():
                print(f"  {step_cfg.path} missing - converting from {step_cfg.stl}")
                try:
                    convert_stl_to_step(step_cfg.stl, step_cfg.path)
                except RuntimeError as e:
                    print(f"  SKIPPING {row_name}: STL conversion failed: {e}")
                    continue
            else:
                print(
                    f"  SKIPPING {row_name}: {step_cfg.path} missing "
                    "and no STL fallback"
                )
                continue
        cap: Part = import_step(step_cfg.path)  # type: ignore[assignment]
        if step_cfg.rotation != 0:
            cap = Rot(0, 0, step_cfg.rotation) * cap
        bbox = cap.bounding_box()
        cap = Pos(-bbox.center().X, -bbox.center().Y, -bbox.min.Z) * cap
        # Update bbox after repositioning
        bbox = cap.bounding_box()

        # Stem plane: based on the largest face (inside bottom of keycap)
        internal_face = max(cap.faces(), key=lambda f: f.area)
        n: Vector = internal_face.normal_at()
        pln: Plane = Plane(
            origin=Vector(0, 0, internal_face.center().Z),
            z_dir=-n,
            x_dir=Vector(1, 0, 0),
        )

        choc_stem: Part | None = None
        if not step_cfg.has_stem:
            choc_stem = pln.location * choc_stem_base
            choc_stem.color = Color("gray")
            choc_stem.label = "stem"

        # Legend plane: based on the lowest point of the top surface near the center
        legend_z = find_legend_plane_z(cap, bbox)
        text_pln: Plane = Plane(
            origin=Vector(0, 0, legend_z - 0.4),
            z_dir=Vector(0, 0, 1),
            x_dir=Vector(1, 0, 0),
        )

        for entry in legend_entries:
            legend_desc = build_legend_desc(entry)
            if not legend_desc:
                print("  Skipping: no legend specified")
                continue
            if ONLY_KEYS and (entry.name or entry.primary) not in ONLY_KEYS:
                print(f"  Skipping {entry.name or entry.primary} (not in ONLY_KEYS)")
                continue

            print(
                f"  Creating keycap with legend: {legend_desc}"
                + (" (mirrored)" if entry.mirror_x else "")
            )

            # Resolve fonts with fallbacks
            primary_font = entry.primary_font or settings.font
            primary_font_size = entry.primary_font_size or settings.primary_font_size
            secondary_font = entry.secondary_font or primary_font
            tertiary_font = entry.tertiary_font or settings.font

            print("    Mirroring cap/stem...")
            # Mirror cap and stem BEFORE boolean operations, so legend aligns correctly
            working_cap: Part
            working_stem: Part | None = None
            if entry.mirror_x:
                working_cap = mirror(cap, Plane.YZ)  # type: ignore[assignment]
                if choc_stem is not None:
                    working_stem = mirror(choc_stem, Plane.YZ)  # type: ignore[assignment]
            else:
                working_cap = cap
                working_stem = choc_stem
            if working_stem is not None:
                working_stem.color = Color("gray")
                working_stem.label = "stem"

            text_solid: Part | None = None

            def make_text_piece(
                char: str,
                font: str,
                size: float,
                x_off: float,
                y_off: float,
                bold: float,
            ) -> Part:
                """Build one legend piece anchored to its own local surface.

                Each piece is placed 0.4mm below the lowest surface point
                under its OWN footprint, keeping the carve depth uniform so
                enclosed counters (O, @, ...) never pierce the top wall and
                detach as islands.
                """
                pln = Plane(
                    origin=text_pln.origin
                    + text_pln.x_dir * x_off
                    + text_pln.y_dir * y_off,
                    z_dir=text_pln.z_dir,
                    x_dir=text_pln.x_dir,
                )
                with BuildSketch(pln) as bs:
                    Text(
                        char,
                        font_size=size,
                        font=font,
                        align=(Align.CENTER, Align.CENTER),
                    )
                sketch = bs.sketch
                if bold:
                    try:
                        sketch = offset(sketch, amount=bold, kind=Kind.ARC)
                    except Exception:
                        # Some outlines (e.g. zeta's curl) break 2D offset -
                        # dilate by unioning shifted copies instead
                        print("    (bold via union dilation)")
                        base = sketch
                        for i in range(8):
                            a = i * math.pi / 4
                            sketch = sketch + Pos(
                                bold * math.cos(a), bold * math.sin(a)
                            ) * base
                solid = extrude(sketch, amount=6, dir=text_pln.z_dir, both=False)
                local_z = find_legend_plane_z(
                    working_cap, bbox, footprint=solid.bounding_box()
                )
                dz = local_z - legend_z
                if abs(dz) > 1e-6:
                    solid = Pos(0, 0, dz) * solid
                return solid  # type: ignore[return-value]

            if entry.primary and entry.secondary:
                print("    Creating primary text...")
                px = (
                    entry.primary_x_offset
                    if entry.primary_x_offset is not None
                    else settings.primary_x_offset
                )
                py = (
                    entry.primary_y_offset
                    if entry.primary_y_offset is not None
                    else settings.primary_y_offset
                )
                text_solid = make_text_piece(
                    entry.primary,
                    primary_font,
                    primary_font_size,
                    px,
                    py,
                    settings.bold_offset,
                )
                print("    Creating secondary text...")
                secondary_solid = make_text_piece(
                    entry.secondary,
                    secondary_font,
                    entry.secondary_font_size or settings.secondary_font_size,
                    entry.secondary_x_offset
                    if entry.secondary_x_offset is not None
                    else settings.secondary_x_offset,
                    entry.secondary_y_offset
                    if entry.secondary_y_offset is not None
                    else settings.secondary_y_offset,
                    0.0,
                )
                text_solid = text_solid + secondary_solid  # type: ignore[assignment]

                if entry.tertiary:
                    print("    Creating tertiary text...")
                    tertiary_solid = make_text_piece(
                        entry.tertiary,
                        tertiary_font,
                        settings.tertiary_font_size,
                        settings.tertiary_x_offset,
                        settings.tertiary_y_offset,
                        0.0,
                    )
                    text_solid = text_solid + tertiary_solid  # type: ignore[assignment]

            elif entry.primary:
                print("    Creating primary text (centered)...")
                text_solid = make_text_piece(
                    entry.primary,
                    primary_font,
                    primary_font_size,
                    0.0,
                    0.0,
                    settings.bold_offset,
                )

            elif entry.secondary:
                print("    Creating secondary text (centered)...")
                text_solid = make_text_piece(
                    entry.secondary,
                    secondary_font,
                    settings.secondary_font_size,
                    0.0,
                    0.0,
                    0.0,
                )

            if entry.quaternary and text_solid is not None:
                print("    Creating quaternary text...")
                quaternary_solid = make_text_piece(
                    entry.quaternary,
                    entry.quaternary_font or settings.font,
                    entry.quaternary_font_size or settings.quaternary_font_size,
                    settings.quaternary_x_offset,
                    settings.quaternary_y_offset,
                    0.0,
                )
                text_solid = text_solid + quaternary_solid  # type: ignore[assignment]

            # Bound the carve depth: subtract a downshifted copy of the cap
            # so the cut follows the top surface and never goes deeper than
            # max_carve_depth - enclosed glyph counters (O, @, &) would
            # otherwise pierce the wall on curved tops and detach as islands
            print("    Bounding carve depth...")
            depth_bound = (
                text_solid - Pos(0, 0, -settings.max_carve_depth) * working_cap
            )
            if depth_bound is not None and list(depth_bound.solids()):
                text_solid = depth_bound  # type: ignore[assignment]
            else:
                print("    WARNING: depth bounding failed - using full-depth carve")

            print("    Boolean subtract (hole_cap)...")
            # Escalating strategies: tangent tool faces can silently break
            # OCCT booleans; a fuzzy tolerance or a sub-print-resolution
            # nudge (8um) resolves them
            cut_solids: list[Solid] = []
            legend = None
            for strategy, tool in (
                ("exact", text_solid),
                ("nudged", Pos(0.008, 0.008, 0) * text_solid),
            ):
                attempt: Part | Solid | None = working_cap - tool  # type: ignore[operator]
                cut_solids = (
                    list(attempt)
                    if isinstance(attempt, ShapeList)
                    else list(attempt.solids()) if attempt is not None else []
                )
                if not cut_solids:
                    fz = fuzzy_boolean(working_cap, tool, cut=True)
                    cut_solids = list(fz.solids()) if fz is not None else []
                if not cut_solids:
                    continue
                legend = working_cap & tool  # type: ignore[operator]
                if legend is None or not list(legend.solids()):
                    legend = fuzzy_boolean(working_cap, tool, cut=False)
                if legend is not None and list(legend.solids()):
                    if strategy != "exact":
                        print(f"    (used {strategy} boolean strategy)")
                    break
                legend = None
            if not cut_solids or legend is None:
                print(f"    ERROR: booleans failed for '{legend_desc}' - skipping")
                continue
            hole_cap: Part | Solid = max(cut_solids, key=lambda s: s.volume)
            dropped = [s for s in cut_solids if s is not hole_cap]
            if dropped:
                vols = [round(s.volume, 3) for s in dropped]
                print(
                    f"    WARNING: dropped {len(dropped)} island solids {vols} "
                    f"for '{legend_desc}' - possible hole in a glyph counter!"
                )

            print("    Legend created")

            # Mesher exports one 3MF object per solid and reads label/color
            # from each solid - booleans and mirror() return compounds, so
            # stamp every solid or parts come out unnamed and uncolored
            hole_solids: list[Solid] = list(hole_cap.solids())
            legend_solids: list[Solid] = list(legend.solids())
            for s in hole_solids:
                s.color = Color("gray")
                s.label = "cap body"
            for s in legend_solids:
                s.color = Color("black")
                s.label = "legend"
            if not legend_solids:
                print(f"    WARNING: legend '{legend_desc}' is empty - blank cap!")
            stem_solids: list[Solid] = []
            if working_stem is not None:
                stem_solids = list(working_stem.solids())
                for s in stem_solids:
                    s.color = Color("gray")
                    s.label = "stem"

            try:
                show([*hole_solids, *legend_solids, *stem_solids])
                print("    Meshing shapes...")
                m: Mesher = Mesher(unit=Unit.MM)
                m.add_shape(hole_solids, linear_deflection=0.06, angular_deflection=0.3)
                print("    Meshed hole_cap")
                m.add_shape(
                    legend_solids, linear_deflection=0.01, angular_deflection=0.05
                )
                print("    Meshed legend")
                if stem_solids:
                    m.add_shape(
                        stem_solids, linear_deflection=0.06, angular_deflection=0.3
                    )
                    print("    Meshed stem")
                filename = build_filename(entry, row_name)
                m.write(filename)
                bambuify_3mf(
                    filename,
                    {
                        "cap body": settings.body_filament,
                        "legend": settings.legend_filament,
                        "stem": settings.stem_filament,
                    },
                )
                print("    Bambu filament mapping applied")
            except RuntimeError as e:
                print(f"    ERROR: Failed to create mesh for '{legend_desc}': {e}")


if __name__ == "__main__":
    main()
