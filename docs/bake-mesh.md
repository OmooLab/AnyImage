# 烘焙网格

**Bake Mesh** 将 AnyImage 的程序化图片对象固化为带贴图的普通 Mesh，方便继续编辑网格或用于后续制作。

## 使用方法

完成形状和材质调整后，在 Object Mode 中选中对象，右键选择 **AnyImage > Bake Mesh**。

支持 Plane、Depth Plane、Relief Plane、Panorama 和受支持的 Cutout 节点栈。工具会固化当前几何与 UV，整理 Color 贴图，并在需要时烘焙 Tangent Normal。

## 烘焙结果

烘焙在原对象上完成，保留对象、材质和图片的数据身份，并移除已固化的修改器。此后可以进入 Edit Mode 编辑普通网格；如需恢复参数调整，可立即使用 Undo。

材质或图片被其他对象共享时，原位更新也会影响这些使用者。烘焙后仍可在 Shader Editor 的活动 Image Texture 节点上使用图片处理功能。
