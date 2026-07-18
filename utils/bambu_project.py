# SPDX-License-Identifier: MIT
"""Post-process a lib3mf-written 3MF into a Bambu Studio-friendly project.

Bambu Studio assigns filaments per part via ``Metadata/model_settings.config``
(``<metadata key="extruder" value="N"/>`` on each part). It expects one
assembly object whose components are the part meshes. lib3mf instead writes
each mesh as its own build item, so Bambu imports them as separate objects
with no filament mapping and every part must be assigned by hand.

This module rewrites the 3MF in place:
- mesh objects are kept as-is (geometry, names, colors)
- lib3mf's per-mesh component-wrapper objects and build items are replaced by
  a single assembly object referencing all meshes
- ``Metadata/model_settings.config`` is added, mapping each part name to a
  filament/extruder slot
"""

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def _indent(elem: ET.Element, level: int = 0) -> None:
    pad = "\n" + " " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + " "
        for child in elem:
            _indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = pad + " "
        if not elem[-1].tail or not elem[-1].tail.strip():
            elem[-1].tail = pad
    elif level and (not elem.tail or not elem.tail.strip()):
        elem.tail = pad


def bambuify_3mf(path: Path | str, part_extruders: dict[str, int]) -> None:
    """Restructure a 3MF for Bambu Studio with filament assignments.

    Args:
        path: 3MF file written by build123d's Mesher.
        part_extruders: part label -> 1-based filament/extruder slot,
            e.g. {"cap body": 1, "legend": 2, "stem": 1}.
    """
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        entries = {name: z.read(name) for name in z.namelist()}

    ET.register_namespace("", CORE_NS)
    ET.register_namespace(
        "m", "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
    )
    ET.register_namespace(
        "p", "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
    )
    root = ET.fromstring(entries["3D/3dmodel.model"].decode())
    resources = root.find(f"{{{CORE_NS}}}resources")
    build = root.find(f"{{{CORE_NS}}}build")

    # Partition objects: meshes (have geometry) vs lib3mf component wrappers
    mesh_objects = []
    for obj in list(resources.findall(f"{{{CORE_NS}}}object")):
        if obj.find(f"{{{CORE_NS}}}mesh") is not None:
            mesh_objects.append(obj)
        else:
            resources.remove(obj)
    if not mesh_objects:
        raise RuntimeError(f"No mesh objects found in {path}")

    # Single assembly object referencing every mesh. The id must not clash
    # with ANY resource id (lib3mf numbers materials and objects globally).
    assembly_id = (
        max(int(el.get("id")) for el in resources if el.get("id") is not None) + 1
    )
    assembly = ET.SubElement(
        resources, f"{{{CORE_NS}}}object", {"id": str(assembly_id), "type": "model"}
    )
    components = ET.SubElement(assembly, f"{{{CORE_NS}}}components")
    for obj in mesh_objects:
        ET.SubElement(
            components, f"{{{CORE_NS}}}component", {"objectid": obj.get("id")}
        )

    for item in list(build):
        build.remove(item)
    ET.SubElement(build, f"{{{CORE_NS}}}item", {"objectid": str(assembly_id)})

    _indent(root)
    entries["3D/3dmodel.model"] = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root)
    )

    # Bambu part/filament mapping
    object_name = re.sub(r"\.3mf$", "", path.name)
    cfg = ET.Element("config")
    obj_el = ET.SubElement(cfg, "object", {"id": str(assembly_id)})
    ET.SubElement(obj_el, "metadata", {"key": "name", "value": object_name})
    ET.SubElement(obj_el, "metadata", {"key": "extruder", "value": "1"})
    for obj in mesh_objects:
        label = obj.get("name", "part")
        extruder = part_extruders.get(label, 1)
        part = ET.SubElement(
            obj_el, "part", {"id": obj.get("id"), "subtype": "normal_part"}
        )
        ET.SubElement(part, "metadata", {"key": "name", "value": label})
        ET.SubElement(
            part,
            "metadata",
            {"key": "matrix", "value": "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"},
        )
        ET.SubElement(part, "metadata", {"key": "extruder", "value": str(extruder)})
    _indent(cfg)
    entries["Metadata/model_settings.config"] = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(cfg)
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
