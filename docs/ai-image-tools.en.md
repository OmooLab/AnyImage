# AI Tools

Remove an image's background or enlarge a small texture directly in Blender. Both tools support reference images, image models created by AnyImage, and image textures in materials.

On first use, follow the **Set Up AI Server** prompts to download the required environment and models. Once setup is complete, run the tool again. Images are processed locally, so you can work offline.

## Select an image

In the 3D View, select a reference image or image model and open the **AnyImage** context menu. For a material texture, select an **Image Texture** node with an image in the Shader Editor, then open the context menu. Both workflows use still images.

## Remove Background

Choose **Remove Background** to make the background transparent. Place the subject directly into your scene, or use **Cutout** to turn it into a model. Transparent areas are excluded from the shape.

![Use Remove Background to remove the white background and text, keeping the pterosaur](assets/demos/remove-background.gif)

## Upscale

Choose **Upscale** to double the image dimensions. The menu shows the output size: for example, a 512 × 512 image becomes 1024 × 1024. When processing finishes, the current image or texture is updated with the enlarged result.

<!-- TODO: Landscape comparison showing detail before and after upscaling. -->

If the menu item is unavailable, check that the source image's longest edge is smaller than **Max AI Input Size** in the add-on settings.
