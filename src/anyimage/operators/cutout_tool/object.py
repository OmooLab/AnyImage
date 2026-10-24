import bpy
from ...common.material import create_image_material
from ...common.node import load_node_group
from ...common.object import finalize_object_result, modifier_input_identifier, set_modifier_input
from .mesh_object import create_cutout_mesh
from .shape import CUTOUT_NODE_GROUP_NAMES


def create_cutout_modifier(obj, group, shape, gesture, *, thickness_subtype=None):
    modifier = obj.modifiers.new(name=group.name, type="NODES")
    modifier.node_group = group
    modifier.show_group_selector = False
    set_modifier_input(
        modifier,
        modifier_input_identifier(group, "Thickness", subtype=thickness_subtype),
        0.0 if shape == "FLAT" else 1.0,
    )
    if gesture == "POLYLINE":
        set_modifier_input(modifier, modifier_input_identifier(group, "Mode"), 1)
        if shape == "SOLID":
            set_modifier_input(
                modifier, modifier_input_identifier(group, "Thickness", subtype="DISTANCE"), 0.5
            )
    return modifier


def create_shape_object(
    context, source_object, shape, content_bounds, base_shape, *, color_image, gesture="LASSO"
):
    material = create_image_material(source_object.data, color_image, scene=context.scene)
    obj = None
    try:
        obj = create_cutout_mesh(context, source_object, content_bounds, base_shape, material)
        group = load_node_group(CUTOUT_NODE_GROUP_NAMES[shape])
        create_cutout_modifier(obj, group, shape, gesture)
        return finalize_object_result(context, source_object, obj, keep_source=True)
    except Exception:
        if obj is not None:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        if material.users == 0:
            bpy.data.materials.remove(material)
        raise
