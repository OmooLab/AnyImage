# Crop, Combine, and Rectify Images

Once images are in your scene, you can crop them, combine them, or straighten a surface photographed at an angle.

These tools work with reference images (Image Empty). Select an image in **Object Mode**, then choose a tool from the left toolbar in the 3D View. Press **T** to show the toolbar.

## ✂️ Frame Images

Want to keep just part of an image? Choose **Frame Images**, drag out a rectangle, and release to crop to the new frame.

You can also arrange several images in the scene, select them together, adjust the view, and draw a frame. Images inside the frame are combined from the current viewpoint into one image, replacing the selected images. The last selected image must overlap the frame.

<!-- TODO: Landscape demo showing single-image cropping and combining multiple images. -->

## 🖌️ Image Visibility

Use **Image Visibility** to hide part of a background or restore an area you hid earlier. Choose **Lasso**, **Brush**, or **Polyline** at the top, then pick a visibility mode:

| Mode | Effect |
| --- | --- |
| Set | Keep visible areas inside the selection and hide everything outside |
| Extend | Show areas inside the selection and leave other areas unchanged |
| Subtract | Hide areas inside the selection and leave other areas unchanged |

For Lasso and Brush, release the mouse when you finish drawing. For Polyline, click to add points, then press **Enter** or double-click to finish. **Backspace** removes the previous point.

<!-- TODO: Landscape demo showing parts of an image being hidden and restored. -->

## 📐 Rectify

Straighten a door, window, or wall photographed at an angle to use it as a texture. Choose **Rectify** and click the four corners in any order. When the preview appears, move the mouse horizontally to adjust the aspect ratio, then click to confirm.

Press **Backspace** to go back if you make a mistake. Press **Esc** or right-click to cancel.

<!-- TODO: Landscape demo showing four-corner selection and the rectified result. -->
