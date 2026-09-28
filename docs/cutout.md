# Cutout

Cutout 可以圈出图片中的主体，并把它变成一个独立形状。

背景比较复杂时，可以先用 **Remove Background** 得到透明背景，轮廓会更容易选择。

## 圈选主体

选中 Image Empty，右键打开 **AnyImage > Cutout**。

在顶部工具设置中选择 **Lasso** 或 **Polyline**，然后沿主体轮廓圈选。完成后，从弹出的菜单中选择形状。

![使用 Lasso 圈选主体，并打开 Cutout Shape 菜单]()

## 选择形状

- **Flat**：平面的剪贴形状。
- **Solid**：带厚度的剪贴形状。
- **Depth Symmetry**：前后对称的深度形状。
- **Depth Solid**：按图片深度生成的立体形状。

如果轮廓太粗或细节太多，可以调整顶部的 **Edge Length** 和 **Fine Outline**，再重新圈选。
