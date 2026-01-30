from build123d import (
    Align,
    Axis,
    Box,
    BuildSketch,
    Color,
    Cylinder,
    Mesher,
    Part,
    Plane,
    Pos,
    Rot,
    ShapeList,
    Solid,
    Text,
    Vector,
    extrude,
    fillet,
    import_step,
    mirror,
)
from ocp_vscode import Camera, set_defaults, show_all

from utils.mesher_patch import apply_mesher_triangulation_none_guard

apply_mesher_triangulation_none_guard()

set_defaults(reset_camera=Camera.CENTER, helper_scale=1, transparent=False)

# font_name: str = "Open Cherry"
font_name: str = "DIN 1451 Std Engschrift"

# (path, rotation_degrees) - rotation around Z axis before processing
STEP_FILES = {
    # "row_2": ("assets/1u_row_2.step", 0),
    # "row_2_reachy": ("assets/1u_row_2_left_reachy.step", 90),
    # "row_3": ("assets/1u_row_3.step", 90),
    # "row_3_dots": ("assets/1u_row_3_dots.step", 0),
    # "row_3_reachy": ("assets/1u_row_3_reachy.step", 0),
    # "row_4": ("assets/1u_row_4.step", 0),
    "row_4_reachy": ("assets/1u_row_4_reachy.step", 0),
}

# (legend, mirror_x) - mirror_x=True mirrors the final keycap on X axis
LEGENDS = {
    # "row_2": [("I", False)],
    # "row_2": [("Q", False), ("W", False), ("E", False), ("R", False),
    #           ("U", False), ("I", False), ("O", False), ("P", False)],
    # "row_2_reachy": [("T", True), ("Y", False)],
    # "row_3": [
    #     ("A", False),
    #     ("S", False),
    #     ("D", False),
    #     ("K", False),
    #     ("L", False),
    #     (":", False),
    # ],
    # "row_3_dots": [("F", False), ("J", False)],
    # "row_3_reachy": [("G", False), ("H", True)],
    # "row_4": [
    #     ("Z", False),
    #     ("X", False),
    #     ("C", False),
    #     ("V", False),
    #     ("M", False),
    #     ("<", False),
    #     (">", False),
    #     ("/", False),
    # ],
    "row_4_reachy": [("B", False), ("N", True)],
}

# Characters that need safe filenames
FILENAME_MAP = {
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
cross = Box(8.9, 0.5, 0.4, align=(Align.CENTER, Align.CENTER, Align.MAX)) + [
    Pos(0, 0),
    Pos(-8.9 / 2 + 0.25, 0),
    Pos(8.9 / 2 - 0.25),
] * Box(0.5, 3.5, 0.4, align=(Align.CENTER, Align.CENTER, Align.MAX))
stem = Box(1.3, 3, 3.1, align=(Align.CENTER, Align.CENTER, Align.MAX)) - [
    Pos(3.9, 0),
    Pos(-3.9, 0),
] * Cylinder(3.4, 3.1, align=(Align.CENTER, Align.CENTER, Align.MAX))
stem = fillet(stem.edges().group_by(Axis.Z)[:-1], 0.15)
choc_stem_base: Part = cross + [Pos(2.85, 0), Pos(-2.85, 0)] * stem

for row_name, legend_texts in LEGENDS.items():
    print(f"Processing {row_name}...")

    step_path, rotation_deg = STEP_FILES[row_name]
    cap = import_step(step_path)
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

    choc_stem = pln.location * choc_stem_base
    choc_stem.color = Color("gray")
    choc_stem.label = "stem"

    for legend_text, mirror_x in legend_texts:
        print(
            f"  Creating keycap with legend: {legend_text}"
            + (" (mirrored)" if mirror_x else "")
        )

        # Mirror cap and stem BEFORE boolean operations so legend aligns correctly
        if mirror_x:
            working_cap = mirror(cap, Plane.YZ)
            working_stem = mirror(choc_stem, Plane.YZ)
        else:
            working_cap = cap
            working_stem = choc_stem

        text_pln: Plane = Plane(
            origin=pln.origin - n * 0.4, z_dir=pln.z_dir, x_dir=pln.x_dir
        )

        with BuildSketch(text_pln) as bs:
            Text(
                legend_text,
                font_size=8,
                font=font_name,
                align=(Align.CENTER, Align.CENTER),
            )
        text_solid: Part = extrude(bs.sketch, amount=4, dir=text_pln.z_dir, both=False)

        hole_cap: Part | Solid = working_cap - text_solid
        if isinstance(hole_cap, ShapeList):
            hole_cap = max(hole_cap, key=lambda s: s.volume)
        else:
            solids = list(hole_cap.solids())
            if len(solids) > 1:
                hole_cap = max(solids, key=lambda s: s.volume)

        legend = working_cap - hole_cap
        # Filter out the large cap-like solid, keep only the small legend piece(s)
        if isinstance(legend, ShapeList):
            legend = min(legend, key=lambda s: s.volume)
        else:
            solids = list(legend.solids())
            if len(solids) > 1:
                legend = min(solids, key=lambda s: s.volume)

        hole_cap.color = Color("gray")
        hole_cap.label = "cap body"
        legend.color = Color("yellow")
        legend.label = "legend"

        try:
            m: Mesher = Mesher()
            m.add_shape(hole_cap, linear_deflection=0.06, angular_deflection=0.3)
            m.add_shape(legend, linear_deflection=0.01, angular_deflection=0.05)
            m.add_shape(working_stem, linear_deflection=0.06, angular_deflection=0.3)
            safe_legend = FILENAME_MAP.get(legend_text, legend_text)
            m.write(f"results/K_{safe_legend}_{row_name}.3mf")
        except RuntimeError as e:
            print(f"    ERROR: Failed to create mesh for '{legend_text}': {e}")

if __name__ == "__main__":
    show_all()
