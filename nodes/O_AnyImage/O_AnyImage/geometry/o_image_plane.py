from bpy.types import GeometryNodeTree
from omoonodes import geometry as g, TreeBuilder
from omoonodes.builder import CustomGeometryGroup


class OImagePlane(CustomGeometryGroup):
    _name = "O Image Plane"
    _color_tag = "GEOMETRY"
    _tree_properties = {"description": "Build an aspect-adaptive image plane and add optional centered thickness.", "is_modifier": True}

    def _build_group(self, tree: TreeBuilder[GeometryNodeTree]) -> None:
        geometry = tree.inputs.geometry("Geometry", structure_type="SINGLE", force_non_field=True)
        subdivide = tree.inputs.integer("Subdivide", 0, description="Increase mesh density to represent finer shapes. Higher levels create more vertices and require more processing time.", min_value=0, max_value=10, structure_type="SINGLE", force_non_field=True)
        thickness = tree.inputs.float("Thickness", 0.0, min_value=0.0, max_value=10000.0, structure_type="SINGLE", subtype="DISTANCE", force_non_field=True)
        geometry_1 = tree.outputs.geometry("Geometry")

        bounding_box = g.BoundingBox(geometry=geometry)
        bounding_box_1 = g.BoundingBox(geometry=geometry)
        bounding_box_2 = g.BoundingBox(geometry=geometry)
        math_1 = 2.0 ** subdivide
        position = g.Position().o.position
        vector = bounding_box.o.max - bounding_box.o.min
        math_2 = (math_1 * (vector.x / vector.z).max(1.0)).round() + 1.0
        math_3 = (math_1 * (vector.z / vector.x).max(1.0)).round() + 1.0
        math_4 = (thickness / (vector.x / (math_2 - 1.0) * (vector.z / (math_3 - 1.0))).sqrt()).round().max(3.0)
        vector_math = (bounding_box_2.o.min + bounding_box_2.o.max) * 0.5
        transform_geometry = (
            g.Cube(size=g.CombineXYZ(x=vector.x, y=thickness, z=vector.z), vertices_x=math_2, vertices_y=math_4 + 1.0, vertices_z=math_3)
            >> g.StoreNamedAttribute.corner.vector_2d(name="UVMap", value=g.CombineXYZ(x=position.x / vector.x + 0.5, y=position.z / vector.z + 0.5))
            >> g.TransformGeometry(translation=vector_math, mode="Components")
        )
        vector_1 = bounding_box_1.o.max - bounding_box_1.o.min
        vector_2 = bounding_box_2.o.max - bounding_box_2.o.min
        transform_geometry_1 = (
            g.Grid(size_x=vector_2.x, size_y=vector_2.z, vertices_x=math_2, vertices_y=math_3)
            >> g.StoreNamedAttribute.corner.vector_2d(name="UVMap", value=g.CombineXYZ(x=position.x / vector_1.x + 0.5, y=position.y / vector_1.z + 0.5))
            >> g.TransformGeometry(rotation=(1.5707963, 0.0, 0.0), mode="Components")
            >> g.TransformGeometry(translation=vector_math, mode="Components")
        )
        (
            g.JoinGeometry(geometry=(geometry, (thickness > 0.0).switch.geometry(transform_geometry_1, transform_geometry)))
            >> g.SetMaterialIndex()
            >> g.DeleteGeometry.point(selection=g.Compare.integer.less_than(g.Index(), g.DomainSize(geometry=geometry).o.point_count))
            >> geometry_1
        )

ASSET = OImagePlane

ASSET_METADATA = {
    "description": "Build an aspect-adaptive image plane and add optional centered thickness.",
    "catalog_id": "00000000-0000-0000-0000-000000000000",
}
