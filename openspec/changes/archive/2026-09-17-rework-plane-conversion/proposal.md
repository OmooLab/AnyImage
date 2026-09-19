## Why

Plane 转换目前保留了 Image Empty 的原点而不是生成面的中心，Depth Plane 也只有单次挤出的侧壁，默认细分不足以表达深度地形。节点组还重复承担材质赋值，导致接口和对象数据的职责不一致。

## What Changes

- 普通 Plane 和 Depth Plane 在保持世界空间位置不变的同时，把对象原点统一放到面的中心。
- 将 Depth Plane 重建为单面地形体块：固定底面留在原图片平面，`Thickness` 沿正法线移动置换面，中间侧壁环按厚度位置渐变置换。
- 明确 `Thickness` 为基础厚度：`Depth Scale` 为零时，体块厚度等于 `Thickness`。
- 让 `Base Plane Depth` 决定深度图的零位移位置，并限制负向置换不穿过固定底面。
- **BREAKING**：将 Depth Plane 的 `Depth Amount` 改为 `Depth Scale`，将 `Reference Depth` 改为 `Base Plane Depth`，不保留旧接口。
- **BREAKING**：从 `O Mesh Plane` 和 `O Image Depth Plane` 删除 `Material` socket；`O Mesh Plane` 在内部保留输入 Mesh 的材质集合，生成面统一使用第 `0` 个材质槽。
- Depth Plane 通过一次共享的 MoGe-2 预测同时生成 `z-depth.exr`、`depth.json` 和 `tangent-normal.png`，并把 Tangent Normal 接入图像材质。
- Depth Plane 图像材质与 Cutout 统一使用 Principled IOR `1.2`。
- 将 Depth Plane 的默认 `Subdivide` 设为 `6`，在地形细节和求值几何量之间保持平衡。

## Capabilities

### New Capabilities

- `plane-conversion`: 规定 Plane 转换的中心原点、材质职责，以及 Depth Plane 地形体块的几何和控制语义。

### Modified Capabilities

无。

## Impact

- 影响 Plane 转换与 Depth Plane 结果创建；删除 `Material` socket 同时简化剪贴板 Plane 的 Modifier 输入。
- 扩展 Depth Plane Job 的返回产物与 Blender 端材质创建，但继续复用 Cutout 已使用的通用 MoGe-2 Artifact 生成层。
- 重建 `O Mesh Plane` 与 `O Image Depth Plane` 节点资产、验证脚本和发布 `.blend`。
- 更新节点组接口、运行时 Modifier 输入、Blender 求值测试和内部文档。
- 不改变 `z-depth.exr`、Depth Metadata 或 Cutout Job 协议。
