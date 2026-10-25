# Cutout

See something you like in an image? Outline it and place it in your scene! **Cutout** creates a textured shape from your selection. The original image stays in place, ready for another cutout.

## Outline the part you want

Select a reference image (Image Empty) and choose **Cutout** in the left toolbar. Press **T** if the toolbar is hidden.

Choose **Lasso** at the top, drag around the subject, then release. Or choose **Polyline**, click to trace the outline, and press **Enter** to finish. Pick a shape from the menu that appears.

For a busy background, try [Remove Background](ai-image-tools.md) first. Transparent areas are excluded, so your selection does not need to follow every edge closely.

## Choose a shape

### Flat

Keep just the selected outline and texture. Use it for collage elements, standees, or a quick composition with a few shapes.

<!-- TODO: Landscape demo showing a Flat selection and its result. -->

### Solid

Add thickness to the outline to make a small 3D object. After creation, adjust **Thickness** in the modifier. **Balloon** mode rounds out the surface, while **Shell** mode extends it toward the back.

![Left: choosing Solid. Right: the rounded model created from an illustrated head](assets/demos/solid-cutout.webp)

*Left: choosing Solid. Right: the rounded result. Illustration: milkuriem.*

### Depth Solid

Choose this to preserve the depth variation in the image. AI estimates the selection's depth and creates a shape with thickness. Adjust **Depth Scale** in the modifier to control the depth variation.

![Outline the subject, choose Depth Solid, and move the generated model to the side](assets/demos/depth-cutout.gif)

### Depth Symmetry

AI estimates the image's depth and uses it to create a symmetrical shape. Try a side view of a character or animal, then adjust **Direction** in the modifier to orient the symmetry.

![Left: a crocodile reference image. Right: the Depth Symmetry model after adjusting its direction](assets/demos/depth-symmetry-crocodile.webp)

*Left: the crocodile reference. Right: Depth Symmetry.*

Depth Solid and Depth Symmetry require the full edition's AI features. Complete AI setup from the **AnyImage** context menu, then make a selection again to see both options.

## Refine the outline

Adjust these settings at the top, then make your selection again:

| Setting | How to use it |
| --- | --- |
| **Edge Length** | Lower values create a denser mesh with more faces. |
| **Fine Outline** | Enable to preserve outline details and holes; disable to fill holes and simplify the outline. |
| **Alpha Threshold** | Raise it to exclude more translucent edges and clean up small fragments along the outline. |

Once the shape is ready, use [Bake Mesh](bake-mesh.md) to edit its vertices directly.
