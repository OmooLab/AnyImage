# Color Match

Images in your scene have different colors? Pick one as a reference and bring the others closer to its colors and brightness for a more consistent look. Image textures in materials work too.

## Choose a reference image

Press **N** in the 3D View to open the sidebar, then go to **AnyImage > Color Match**. Select a reference from the image gallery. The palette below shows its main colors.

<!-- TODO: Landscape screenshot showing the reference image and palette. -->

## Match a target image

Select the reference image object or AnyImage image model you want to adjust, then right-click and choose **AnyImage > Match Color Reference**. For a material texture, select an **Image Texture** node with an image in the Shader Editor, then run the tool from the context menu.

The reference and target must be different still images. Once the preview appears:

| Action | Adjustment |
| --- | --- |
| Move the mouse horizontally | Color matching strength |
| Move the mouse vertically | Brightness matching strength |
| Hold **Shift** | Fine adjustment |
| Click or press **Enter** | Confirm |
| Right-click or press **Esc** | Cancel |

<!-- TODO: Landscape comparison showing the reference and the target before and after matching. -->

Transparent areas are preserved when you confirm. To try another adjustment, undo and run the tool again.
