# utils/mesher_patch.py

import ctypes
import math
from collections import defaultdict

from lib3mf import Lib3MF
import OCP.TopAbs as ta
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopLoc import TopLoc_Location

TOLERANCE = 1e-6


def _find_boundary_loops(triangles_indices):
    """Find closed loops of boundary edges from triangle index tuples."""
    edge_count = defaultdict(int)

    for idx in triangles_indices:
        edges = [(idx[0], idx[1]), (idx[1], idx[2]), (idx[2], idx[0])]
        for e in edges:
            rev_e = (e[1], e[0])
            if rev_e in edge_count:
                edge_count[rev_e] += 1
            else:
                edge_count[e] += 1

    boundary_edges = {e for e, c in edge_count.items() if c == 1}
    if not boundary_edges:
        return []

    adj = defaultdict(list)
    for e in boundary_edges:
        adj[e[0]].append(e[1])

    loops = []
    used = set()

    for start_edge in boundary_edges:
        if start_edge in used:
            continue
        loop = [start_edge[0], start_edge[1]]
        used.add(start_edge)
        used.add((start_edge[1], start_edge[0]))

        while loop[-1] != loop[0]:
            curr = loop[-1]
            found = False
            for nxt in adj[curr]:
                edge = (curr, nxt)
                rev_edge = (nxt, curr)
                if edge not in used and rev_edge not in used:
                    loop.append(nxt)
                    used.add(edge)
                    used.add(rev_edge)
                    found = True
                    break
            if not found:
                break

        if len(loop) >= 4 and loop[-1] == loop[0]:
            loops.append(loop[:-1])

    return loops


def _fill_loop_with_fan(loop):
    """Fill a boundary loop with fan triangulation.
    
    The loop contains boundary edges in order. For a proper mesh, fill triangles
    must have edges in the OPPOSITE direction of the boundary edges.
    Boundary edges go loop[i] -> loop[i+1], so fill triangles need reversed winding.
    """
    if len(loop) < 3:
        return []
    tris = []
    # Reverse winding: use (loop[0], loop[i+1], loop[i]) instead of (loop[0], loop[i], loop[i+1])
    for i in range(1, len(loop) - 1):
        tris.append((loop[0], loop[i + 1], loop[i]))
    return tris


def apply_mesher_triangulation_none_guard():
    """
    Patch build123d Mesher._mesh_shape to skip faces where OCCT returns
    no triangulation (Triangulation_s == None), preventing NbNodes() crashes.
    Also patches _create_3mf_mesh to fill boundary holes after vertex merging.
    """
    import build123d.mesher as mesher_mod

    Mesher = mesher_mod.Mesher

    def _mesh_shape_guarded(ocp_mesh, linear_deflection, angular_deflection):
        loc = TopLoc_Location()

        BRepMesh_IncrementalMesh(
            theShape=ocp_mesh.wrapped,
            theLinDeflection=linear_deflection,
            isRelative=True,
            theAngDeflection=angular_deflection,
            isInParallel=True,
        )

        vertices = []
        triangles = []
        offset = 0

        for face in ocp_mesh.faces():
            poly = BRep_Tool.Triangulation_s(face.wrapped, loc)
            if poly is None:
                continue

            trsf = loc.Transformation()

            node_count = poly.NbNodes()
            for i in range(1, node_count + 1):
                p = poly.Node(i).Transformed(trsf)
                vertices.append((p.X(), p.Y(), p.Z()))

            reversed_face = face.wrapped.Orientation() == ta.TopAbs_REVERSED
            order = (1, 3, 2) if reversed_face else (1, 2, 3)

            for tri in poly.Triangles():
                triangles.append([tri.Value(i) + offset - 1 for i in order])

            offset += node_count

        # Remove degenerate triangles (duplicate indices)
        triangles = [t for t in triangles if len({t[0], t[1], t[2]}) == 3]
        return vertices, triangles

    def _create_3mf_mesh_patched(ocp_mesh_vertices, triangles):
        digits = -int(round(math.log(TOLERANCE, 10), 1))

        vertex_to_idx = {}
        next_idx = 0
        vert_table = {}

        for i, (x, y, z) in enumerate(ocp_mesh_vertices):
            key = (round(x, digits), round(y, digits), round(z, digits))
            if key not in vertex_to_idx:
                vertex_to_idx[key] = next_idx
                next_idx += 1
            vert_table[i] = vertex_to_idx[key]

        vertices_3mf = [
            Lib3MF.Position((ctypes.c_float * 3)(*v)) for v in vertex_to_idx.keys()
        ]

        c_uint3 = ctypes.c_uint * 3
        triangles_indices = []

        for tri in triangles:
            a, b, c = tri[0], tri[1], tri[2]
            mapped_a = vert_table[a]
            mapped_b = vert_table[b]
            mapped_c = vert_table[c]

            if mapped_a != mapped_b and mapped_b != mapped_c and mapped_c != mapped_a:
                triangles_indices.append((mapped_a, mapped_b, mapped_c))

        # Fill boundary holes
        loops = _find_boundary_loops(triangles_indices)
        for loop in loops:
            fill_tris = _fill_loop_with_fan(loop)
            triangles_indices.extend(fill_tris)

        triangles_3mf = [Lib3MF.Triangle(c_uint3(*idx)) for idx in triangles_indices]

        return (vertices_3mf, triangles_3mf)

    Mesher._mesh_shape = staticmethod(_mesh_shape_guarded)
    Mesher._create_3mf_mesh = staticmethod(_create_3mf_mesh_patched)
