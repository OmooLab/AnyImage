# Convert Images to Meshes

Turn an entire reference image into a textured mesh. Choose a plane, depth plane, relief, or panorama to suit your scene.

Select a still reference image (Image Empty), right-click to open **AnyImage**, and choose one of the conversions below. After conversion, you can keep adjusting the shape in its modifiers.

## Convert to Plane

Turn the image into a rectangular plane with a material, ready to use as a background, a cutout card, or a starting point for a scene. Adjust **Thickness** in the modifier to give it depth.

<!-- TODO: Landscape demo showing a reference image converted into a textured plane. -->

## Convert to Depth Plane

Bring nearby parts of a photo forward and push distant parts back. AI estimates depth and builds a surface using the original image's perspective. Try it with landscapes or rooms to explore new viewpoints in your scene.

![Choose Convert to Depth Plane from the context menu to turn a mountain photo into a 3D surface](assets/demos/convert-depth-plane.gif)

**Depth Scale** controls the depth variation; set it to **0** to return to a plane. **Thickness** adds thickness to the surface.

## Convert to Relief

Turn the image's shapes into raised details on a flat base, suitable for reliefs and decorative panels. Use **Depth Scale** to adjust the relief height and **Thickness** to adjust the base thickness.

<!-- TODO: Landscape demo showing a reference image converted into a relief. -->

## Convert to Panorama

Start with a **2:1 equirectangular panorama** and turn it into a surrounding scene with depth. Move the viewpoint inside the result to look around.

<!-- TODO: Landscape demo showing a panorama converted into a scene with depth. -->

**Depth Scale** adjusts the depth variation. At **0**, the result is a spherical panorama whose size is controlled by **Dome Radius**. Images with other aspect ratios are center-cropped to 2:1 first.

## Keep working with the result

Depth Plane, Relief, and Panorama require the full edition's AI features. On first use, follow the prompts to set up the environment and models.

Once the shape is ready, use [Bake Mesh](bake-mesh.md) to edit the mesh directly. To use only part of an image, try [Cutout](cutout.md).
