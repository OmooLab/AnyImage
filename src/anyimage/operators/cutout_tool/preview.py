"""Lightweight target-density shading inside the Cutout selection."""

from mathutils import Matrix


def screen_to_grid_matrix(region_size, perspective, world_matrix, edge_length):
    """Map screen pixels to homogeneous, world-sized image-plane grid coordinates."""
    from .geometry import metric_transform, world_plane_metric

    width, height = region_size
    projected = perspective @ world_matrix
    plane_to_clip = Matrix(tuple(
        tuple(projected[row][column] for column in (0, 1, 3))
        for row in (0, 1, 3)
    ))
    screen_to_clip = Matrix(((2 / width, 0, -1), (0, 2 / height, -1), (0, 0, 1)))
    metric, _ = world_plane_metric(world_matrix)
    transform = metric_transform(metric).T / edge_length
    plane_to_grid = Matrix((
        (*transform[0], 0), (*transform[1], 0), (0, 0, 1),
    ))
    return plane_to_grid @ plane_to_clip.inverted() @ screen_to_clip


class CutoutGridPreview:
    """Reuse the fill batch and shade a triangular lattice in one draw call."""

    def __init__(self):
        self.shader = None
        self.batch = None
        self.triangles = None

    def draw(self, triangles, color, screen_to_grid):
        import gpu
        from gpu_extras.batch import batch_for_shader

        if self.shader is None:
            interface = gpu.types.GPUStageInterfaceInfo("anyimage_cutout_grid")
            interface.smooth("VEC3", "gridPosition")
            info = gpu.types.GPUShaderCreateInfo()
            info.push_constant("MAT4", "ModelViewProjectionMatrix")
            info.push_constant("MAT3", "screenToGrid")
            info.push_constant("VEC4", "color")
            info.vertex_in(0, "VEC2", "pos")
            info.vertex_out(interface)
            info.fragment_out(0, "VEC4", "fragColor")
            info.vertex_source("""
                void main() {
                    gridPosition = screenToGrid * vec3(pos, 1.0);
                    gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
                }
            """)
            info.fragment_source("""
                void main() {
                    vec2 p = gridPosition.xy / gridPosition.z;
                    const float height = 0.8660254;
                    vec3 grid = vec3(p.y / height,
                        p.x + p.y / (2.0 * height),
                        p.x - p.y / (2.0 * height));
                    vec3 footprint = max(fwidth(grid), vec3(0.00001));
                    vec3 distance = abs(fract(grid + 0.5) - 0.5) / footprint;
                    vec3 lines = (1.0 - smoothstep(vec3(0.0), vec3(1.0), distance))
                        * smoothstep(vec3(3.0), vec3(8.0), 1.0 / footprint);
                    float line = max(lines.x, max(lines.y, lines.z));
                    fragColor = vec4(color.rgb * mix(1.0, 0.55, line),
                        color.a + 0.04 * line);
                }
            """)
            self.shader = gpu.shader.create_from_info(info)
        shader = self.shader
        if triangles is not self.triangles:
            self.batch = batch_for_shader(shader, "TRIS", {"pos": triangles})
            self.triangles = triangles
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix",
                             gpu.matrix.get_projection_matrix() @ gpu.matrix.get_model_view_matrix())
        shader.uniform_float("screenToGrid", screen_to_grid)
        shader.uniform_float("color", color)
        gpu.state.blend_set("ALPHA")
        try:
            self.batch.draw(shader)
        finally:
            gpu.state.blend_set("NONE")
