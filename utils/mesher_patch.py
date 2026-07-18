# SPDX-License-Identifier: MIT

import ctypes
import math
from collections import defaultdict

from lib3mf import Lib3MF
import OCP.TopAbs as ta
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopLoc import TopLoc_Location

# Vertex merge grid for 3MF export. 0.1um: far below print resolution but
# coarse enough to collapse micro-butterflies left by booleans against
# stem-in-mesh geometry (1e-6 leaves them non-manifold and lib3mf rejects
# the mesh).
TOLERANCE = 1e-4


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

        # Remove fin pairs: coincident faces (e.g. baked-in stems touching
        # the cap interior) merge into duplicated triangles - zero-volume
        # fins that make the mesh non-manifold. Drop them pairwise; an odd
        # count keeps one triangle (it is a real surface face).
        fin_groups = defaultdict(list)
        for tri in triangles_indices:
            fin_groups[frozenset(tri)].append(tri)
        triangles_indices = [
            group[0] for group in fin_groups.values() if len(group) % 2 == 1
        ]

        # Fill boundary holes
        loops = _find_boundary_loops(triangles_indices)
        for loop in loops:
            fill_tris = _fill_loop_with_fan(loop)
            triangles_indices.extend(fill_tris)

        # Split pinch (non-manifold) edges: boolean cuts grazing facet edges
        # can leave an edge shared by 4 triangles (2 per direction - an
        # hourglass pinch), which lib3mf rejects. Repair by vertex-fan
        # splitting: at each pinch vertex, group incident triangles into
        # sheets connected only through manifold (2-triangle) edges, and give
        # every sheet beyond the first its own copy of the vertex. Whole
        # sheets are rewired together, so no boundary edges are created and
        # coordinates are unchanged.
        positions = list(vertex_to_idx.keys())

        def _edge_counts():
            counts = defaultdict(int)
            for tri in triangles_indices:
                for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                    counts[(a, b) if a < b else (b, a)] += 1
            return counts

        edge_counts = _edge_counts()
        pinch_vertices = {
            v for e, n in edge_counts.items() if n > 2 for v in e
        }
        for v in sorted(pinch_vertices):
            incident = [
                t_idx
                for t_idx, tri in enumerate(triangles_indices)
                if v in tri
            ]
            # Union-find over incident triangles, connected only through
            # manifold edges containing v
            parent = {t: t for t in incident}

            def _find(t):
                while parent[t] != t:
                    parent[t] = parent[parent[t]]
                    t = parent[t]
                return t

            edge_map = defaultdict(list)
            for t_idx in incident:
                for u in triangles_indices[t_idx]:
                    if u != v:
                        edge = (v, u) if v < u else (u, v)
                        if edge_counts[edge] == 2:
                            edge_map[edge].append(t_idx)
            for tris_on_edge in edge_map.values():
                for other in tris_on_edge[1:]:
                    ra, rb = _find(tris_on_edge[0]), _find(other)
                    if ra != rb:
                        parent[rb] = ra
            sheets = defaultdict(list)
            for t_idx in incident:
                sheets[_find(t_idx)].append(t_idx)
            for sheet in list(sheets.values())[1:]:
                new_v = len(vertices_3mf)
                vertices_3mf.append(
                    Lib3MF.Position((ctypes.c_float * 3)(*positions[v]))
                )
                positions.append(positions[v])
                for t_idx in sheet:
                    triangles_indices[t_idx] = tuple(
                        new_v if u == v else u for u in triangles_indices[t_idx]
                    )
            if len(sheets) > 1:
                edge_counts = _edge_counts()

        triangles_3mf = [Lib3MF.Triangle(c_uint3(*idx)) for idx in triangles_indices]

        return (vertices_3mf, triangles_3mf)

    Mesher._mesh_shape = staticmethod(_mesh_shape_guarded)
    Mesher._create_3mf_mesh = staticmethod(_create_3mf_mesh_patched)
