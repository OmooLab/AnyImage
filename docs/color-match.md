# 颜色匹配

**Match Color Reference** 根据参考图片调整目标图片的色彩与亮度，适合统一场景中多张图片的视觉风格。

## 选择参考图片

在 3D View 中按 **N** 打开侧栏，进入 **AnyImage > Color Match**。从图片画廊中选择参考图片，下方色板会显示它的主要颜色。参考图片随当前 Scene 保存。

## 匹配目标图片

选中 Image Empty 或 AnyImage 创建的图片 Mesh，右键选择 **AnyImage > Match Color Reference**。也可以在 Shader Editor 中选中带图片的 Image Texture 节点，从右键菜单执行。

参考与目标需要是不同的静态图片。预览出现后：

- 左右移动鼠标调整颜色匹配强度。
- 上下移动鼠标调整亮度匹配强度。
- 按住 **Shift** 精细调整。
- 单击或按 **Enter** 确认；右键或 **Esc** 取消。

确认后更新目标图片，保留透明度；可使用 Blender 的 Undo 撤销。
