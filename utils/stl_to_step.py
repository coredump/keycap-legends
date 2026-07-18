# SPDX-License-Identifier: MIT
"""STL to STEP conversion producing a refined, OCCT-valid solid.

Replaces the manual FreeCAD Part-workbench process (mesh to shape /
shape to solid / refine shape). The keycap STLs contain mesh defects -
sliver triangles with near-coincident vertices, zero-length edges,
back-to-back fin triangles and loose debris flakes - that FreeCAD's
coarse 0.10 sewing tolerance papered over by collapsing geometry,
yielding OCCT-invalid solids. Instead the mesh is repaired first
(trimesh), then sewn watertight at tight tolerance.
"""

import time
from pathlib import Path

import numpy as np
import trimesh
from build123d import Solid, export_step
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeSolid,
    BRepBuilderAPI_Sewing,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_SHELL, TopAbs_ShapeEnum
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

# Collapse edges shorter than 0.1um: removes zero-length edges and welded
# slivers. Larger values (tested 0.5um+) fold micro-facet regions and
# break watertightness.
EDGE_COLLAPSE_EPS = 1e-4
SEW_TOLERANCE = 1e-6


def _collapse_short_edges(mesh: trimesh.Trimesh, eps: float) -> trimesh.Trimesh:
    """Union-find weld of sub-eps edges; drops faces that collapse."""
    v = np.asarray(mesh.vertices).copy()
    f = np.asarray(mesh.faces).copy()
    for _ in range(10):
        edges = np.vstack((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]))
        lengths = np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1)
        short = edges[lengths < eps]
        if len(short) == 0:
            break
        parent = np.arange(len(v))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for a, b in short:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
        mapping = np.array([find(i) for i in range(len(v))])
        f = mapping[f]
        keep = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 2] != f[:, 0])
        f = f[keep]
    repaired = trimesh.Trimesh(vertices=v, faces=f, process=False)
    repaired.remove_unreferenced_vertices()
    return repaired


def _repair_mesh(stl_path: Path) -> trimesh.Trimesh:
    """Load and repair an STL into a watertight single-body mesh."""
    mesh = trimesh.load(str(stl_path), force="mesh")
    n0 = len(mesh.faces)
    mesh.merge_vertices(merge_tex=True, merge_norm=True, digits_vertex=4)
    mesh = _collapse_short_edges(mesh, EDGE_COLLAPSE_EPS)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    parts = mesh.split(only_watertight=False)
    if len(parts) > 1:
        parts = sorted(parts, key=lambda p: len(p.faces), reverse=True)
        dropped = sum(len(p.faces) for p in parts[1:])
        print(f"    Dropped {len(parts) - 1} debris bodies ({dropped} faces)")
        mesh = parts[0]
    trimesh.repair.fill_holes(mesh)
    trimesh.repair.fix_normals(mesh)
    print(f"    Repaired mesh: {n0} -> {len(mesh.faces)} triangles")
    if not mesh.is_watertight:
        raise RuntimeError(f"Mesh not watertight after repair: {stl_path.name}")
    return mesh


def convert_stl_to_step(stl_path: Path | str, step_path: Path | str) -> None:
    """Convert an STL mesh to a refined solid STEP file.

    Raises RuntimeError unless the mesh becomes a single closed, valid
    solid - a broken STEP is worse than no STEP.
    """
    stl_path = Path(stl_path)
    step_path = Path(step_path)
    start = time.monotonic()

    mesh = _repair_mesh(stl_path)

    # Mesh triangles -> planar faces -> sewn shell
    print(f"    Sewing (tolerance {SEW_TOLERANCE})...")
    verts = [gp_Pnt(*map(float, v)) for v in np.asarray(mesh.vertices)]
    sewing = BRepBuilderAPI_Sewing(SEW_TOLERANCE)
    for tri in mesh.faces:
        polygon = BRepBuilderAPI_MakePolygon(
            verts[tri[0]], verts[tri[1]], verts[tri[2]], Close=True
        )
        face_maker = BRepBuilderAPI_MakeFace(polygon.Wire(), True)
        if face_maker.IsDone():
            sewing.Add(face_maker.Face())
    sewing.Perform()
    if sewing.NbFreeEdges() > 0:
        raise RuntimeError(
            f"{sewing.NbFreeEdges()} free edges after sewing {stl_path.name}"
        )
    shells = []
    explorer = TopExp_Explorer(sewing.SewedShape(), TopAbs_SHELL)
    while explorer.More():
        shells.append(TopoDS.Shell_s(explorer.Current()))
        explorer.Next()
    if len(shells) != 1:
        raise RuntimeError(
            f"Sewing produced {len(shells)} shells (expected 1) for {stl_path.name}"
        )

    # Shape to solid, with outward orientation
    solid = BRepBuilderAPI_MakeSolid(shells[0]).Solid()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid, props)
    if props.Mass() < 0:
        solid = TopoDS.Solid_s(solid.Reversed())

    # Refine: merge coplanar faces (FreeCAD's refine shape / removeSplitter)
    print("    Refining (UnifySameDomain)...")
    unify = ShapeUpgrade_UnifySameDomain(solid, True, True, False)
    unify.Build()
    refined = unify.Shape()
    if refined.ShapeType() != TopAbs_ShapeEnum.TopAbs_SOLID:
        raise RuntimeError(
            f"Refine returned {refined.ShapeType()} instead of a solid "
            f"for {stl_path.name}"
        )
    refined_solid = TopoDS.Solid_s(refined)

    if not BRepCheck_Analyzer(refined_solid).IsValid():
        raise RuntimeError(f"Converted solid failed BRepCheck for {stl_path.name}")

    result = Solid(refined_solid)
    export_step(result, str(step_path))
    elapsed = time.monotonic() - start
    print(
        f"    Wrote {step_path.name}: volume={result.volume:.2f}mm3 "
        f"faces={len(result.faces())} ({elapsed:.1f}s)"
    )
