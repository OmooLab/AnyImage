# Bake Mesh

Ready to move vertices or change the topology of a shape made from an image? **Bake Mesh** turns its current shape and textures into a regular, editable mesh.

## How to use it

Finish adjusting the shape and material, select the model in **Object Mode**, then right-click and choose **AnyImage > Bake Mesh**. Once it finishes, press **Tab** to enter Edit Mode and continue editing the mesh.

Supported shapes include **Plane**, **Depth Plane**, **Relief**, **Panorama**, and the Cutout shapes **Solid**, **Depth Solid**, and **Depth Symmetry**.

<!-- TODO: Landscape demo showing mesh editing in Edit Mode after baking. -->

## The baked result

Baking prepares UVs and color textures, and generates a tangent-space normal map when needed. Baked modifiers are removed, fixing the original shape parameters in place. To return to adjusting those parameters, undo immediately.

Shared materials and images that need updating are copied for the current object, leaving other objects unchanged. After baking, you can still select an **Image Texture** node in the Shader Editor to match colors, remove the background, or upscale the texture.
