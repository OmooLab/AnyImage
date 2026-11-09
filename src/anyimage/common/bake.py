"""Evaluate texture bakes in an isolated Blender scene."""

from contextlib import ExitStack, contextmanager

import bpy


BAKE_MARGIN = 4


@contextmanager
def bake_context(mesh, material, matrix):
    """Isolate baking and release resources even when scene setup fails."""
    with ExitStack() as cleanup:
        scene = bpy.data.scenes.new("Any Image mesh bake")
        cleanup.callback(bpy.data.scenes.remove, scene)
        obj = bpy.data.objects.new("Any Image mesh bake", mesh)
        cleanup.callback(bpy.data.objects.remove, obj, do_unlink=True)
        obj.matrix_world = matrix
        scene.collection.objects.link(obj)
        mesh.materials.clear()
        mesh.materials.append(material)
        layer = scene.view_layers[0]
        layer.objects.active = obj
        obj.select_set(True, view_layer=layer)
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False
        window = bpy.context.window
        if window:
            cleanup.callback(setattr, window, "scene", window.scene)
            window.scene = scene
        with bpy.context.temp_override(scene=scene, view_layer=layer, object=obj,
                                       active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            yield
