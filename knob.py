# SPDX-License-Identifier: MIT
"""EC11 encoder knob: Ø22mm inset coin-edge knob with carved Ω legend.

Parametric, no STEP input. Sits near-flush inside a Ø23mm case hole.
Exports results/K_knob_omega.3mf with the same filament labels as the caps.
"""

import argparse
import math

from build123d import (
    Align,
    Axis,
    BuildLine,
    BuildSketch,
    Circle,
    Color,
    Cylinder,
    Locations,
    Mesher,
    Mode,
    Plane,
    Polyline,
    Pos,
    Rectangle,
    Solid,
    Sphere,
    Text,
    Unit,
    chamfer,
    extrude,
    fillet,
    make_face,
)

from config import load_config
from utils.bambu_project import bambuify_3mf
from utils.mesher_patch import apply_mesher_triangulation_none_guard

# Body
KNOB_DIA = 22.0  # 0.5mm radial clearance in the 23mm hole
KNOB_H = 14.0
BOTTOM_CHAMFER = 0.5
TOP_FILLET = 0.8

# Dish (spherical concave top)
DISH_DEPTH = 1.2
DISH_DIA = 19.0

# Coin-edge knurl: grooves cut into the upper band of the wall
KNURL_COUNT = 60
KNURL_TOOL_DIA = 1.0
KNURL_DEPTH = 0.35
KNURL_BAND_H = 6.0

# Bore for 6mm EC11 D-shaft (light FDM press fit).
# The shaft flat is only ~7mm long, so the D-profile is limited to the top
# of the bore; below it a round clearance section slides over the round
# shaft portion, letting the tip reach the bore ceiling.
BORE_DIA = 6.15
BORE_FLAT = 4.65  # flat-to-round distance across the D
BORE_DEPTH = 10.5
D_SECTION_LEN = 6.5  # < 7mm flat length so the tip bottoms on the ceiling
ROUND_CLEAR_DIA = 6.3  # clearance over the round shaft section
NUT_CB_DIA = 12.0  # counterbore clearing the M7 bushing nut
NUT_CB_DEPTH = 2.5

# Legend defaults (the original omega knob); override via CLI
LEGEND_GLYPH = "Ω"
LEGEND_FONT = "Noto Sans"
LEGEND_HEIGHT = 9.0  # target physical glyph height in mm
LEGEND_DEPTH = 0.8  # carve below the dish low point
LEGEND_MAX_DIA = 17.0  # glyph bbox diagonal must fit inside the dish


def build_body() -> Solid:
    body = Cylinder(
        KNOB_DIA / 2, KNOB_H, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )

    # Concave spherical dish: sphere sized from chord/sagitta
    a = DISH_DIA / 2
    sphere_r = (a * a + DISH_DEPTH * DISH_DEPTH) / (2 * DISH_DEPTH)
    dish_tool = Pos(0, 0, KNOB_H - DISH_DEPTH + sphere_r) * Sphere(sphere_r)
    body = body - dish_tool

    # Soften the top rim and the dish edge before texturing
    top_edges = body.edges().group_by(Axis.Z)[-1]
    body = fillet(top_edges, TOP_FILLET)

    # Coin-edge grooves around the exposed upper band
    tool_r = KNURL_TOOL_DIA / 2
    orbit_r = KNOB_DIA / 2 + tool_r - KNURL_DEPTH
    cutter = Cylinder(
        tool_r,
        KNURL_BAND_H + TOP_FILLET,
        align=(Align.CENTER, Align.CENTER, Align.MAX),
    )
    for i in range(KNURL_COUNT):
        t = (Pos(orbit_r, 0, KNOB_H) * cutter).rotate(
            Axis.Z, 360 * i / KNURL_COUNT
        )
        body = body - t

    # Blind stepped bore from the bottom: nut counterbore, round clearance,
    # then the D-profile engaging the shaft flat at the top
    with BuildSketch() as bore_sk:
        Circle(BORE_DIA / 2)
        # Cut everything beyond the flat: rectangle covering the segment
        with Locations(Pos(BORE_FLAT - BORE_DIA / 2, 0)):
            Rectangle(
                BORE_DIA,
                BORE_DIA,
                align=(Align.MIN, Align.CENTER),
                mode=Mode.SUBTRACT,
            )
    d_section = extrude(
        Plane.XY.offset(BORE_DEPTH - D_SECTION_LEN) * bore_sk.sketch,
        D_SECTION_LEN,
    )
    round_section = Cylinder(
        ROUND_CLEAR_DIA / 2,
        BORE_DEPTH - D_SECTION_LEN,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    nut_cb = Cylinder(
        NUT_CB_DIA / 2,
        NUT_CB_DEPTH,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    body = body - d_section - round_section - nut_cb

    bottom_edges = body.edges().group_by(Axis.Z)[0]
    body = chamfer(bottom_edges, BOTTOM_CHAMFER)
    return body


def build_legend(
    body: Solid,
    glyph: str = LEGEND_GLYPH,
    font: str = LEGEND_FONT,
    height: float = LEGEND_HEIGHT,
) -> tuple[Solid, Solid]:
    """Carve the glyph into the dish; return (carved body, legend solid)."""
    # Measure the glyph and scale font size to the target physical height,
    # then cap so the bbox diagonal stays inside the dish
    probe_size = 10.0
    with BuildSketch() as probe:
        Text(glyph, font=font, font_size=probe_size)
    bb = probe.sketch.bounding_box()
    font_size = probe_size * height / bb.size.Y
    diag = math.hypot(bb.size.X, bb.size.Y) * font_size / probe_size
    if diag > LEGEND_MAX_DIA:
        font_size *= LEGEND_MAX_DIA / diag
        print(f"  (glyph scaled down to fit dish: {font_size:.2f})")

    with BuildSketch(Plane.XY.offset(KNOB_H)) as sk:
        Text(glyph, font=font, font_size=font_size)
    # center on the dish by actual ink bbox - glyph side bearings and
    # baseline geometry can put the visual center well off the anchor
    sbb = sk.sketch.bounding_box()
    sketch = Pos(-sbb.center().X, -sbb.center().Y) * sk.sketch

    dish_low = KNOB_H - DISH_DEPTH
    cut_bottom = dish_low - LEGEND_DEPTH
    tool = extrude(sketch, -(KNOB_H - cut_bottom))
    legend = tool & body  # top follows the dish, bottom flat at cut_bottom
    carved = body - tool
    return carved, legend


def main() -> None:
    parser = argparse.ArgumentParser(description="EC11 knob generator")
    parser.add_argument("--glyph", default=LEGEND_GLYPH)
    parser.add_argument("--font", default=LEGEND_FONT)
    parser.add_argument("--height", type=float, default=LEGEND_HEIGHT)
    parser.add_argument("--name", default="omega", help="output name suffix")
    args = parser.parse_args()

    apply_mesher_triangulation_none_guard()
    settings = load_config().settings

    print("Building knob body...")
    body = build_body()
    print(f"Carving legend '{args.glyph}' ({args.font}, {args.height}mm)...")
    carved, legend = build_legend(body, args.glyph, args.font, args.height)

    body_solids = list(carved.solids())
    legend_solids = list(legend.solids())
    for s in body_solids:
        s.color = Color("gray")
        s.label = "cap body"
    for s in legend_solids:
        s.color = Color("black")
        s.label = "legend"
    if not legend_solids:
        print("WARNING: legend came out empty!")
    extra = [s for s in body_solids if s.volume < 1.0]
    if extra:
        print(f"WARNING: {len(extra)} small stray solids in body")

    print("Meshing...")
    m = Mesher(unit=Unit.MM)
    m.add_shape(body_solids, linear_deflection=0.06, angular_deflection=0.3)
    m.add_shape(legend_solids, linear_deflection=0.01, angular_deflection=0.05)
    filename = f"results/K_knob_{args.name}.3mf"
    m.write(filename)
    bambuify_3mf(
        filename,
        {
            "cap body": settings.body_filament,
            "legend": settings.legend_filament,
        },
    )
    print(f"Wrote {filename}")


if __name__ == "__main__":
    main()
