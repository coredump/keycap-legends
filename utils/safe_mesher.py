# utils/safe_mesher.py

import OCP.TopAbs as ta
from build123d import Mesher
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopLoc import TopLoc_Location


class SafeMesher(Mesher):
    @staticmethod
    def _mesh_shape(ocp_mesh, linear_deflection, angular_deflection):
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
