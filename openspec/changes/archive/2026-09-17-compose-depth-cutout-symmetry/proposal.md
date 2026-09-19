## Why

Depth Cutout 已负责深度置换及 Balloon / Shell 成形，对称应当作为后续几何操作复用这些结果。独立实验已验证零厚度 Cutout 接对称节点可以复现原 Depth Symmetry 的 Projected 构成方式，同时发现薄 Shell 的 Normal Smooth 被厚度权重压低，需要修正。

## What Changes

- 保留 Depth Solid、Depth Symmetry 两个入口；Depth Symmetry 创建串联的 `O Image Depth Cutout`（两个模式的 Thickness 均为 0）和 `O Image Cutout Symmetry`。
- Cutout 节点资产中 Balloon / Shell 两种 Thickness 的默认值均为 0；Depth Solid 创建时分别设置为 1 和 0.2，Depth Symmetry 使用零厚度默认值。
- **BREAKING**：`O Image Cutout Symmetry` 改为接收已成形几何的对称节点，提取原 Projected 的方向对齐、偏移、负侧面移除、镜像及边界直壁补面逻辑；移除图像置换和 Mode。
- 对称节点提供 Geometry、Symmetry Direction、Depth Offset、Fill Sides、Fill Smooth；始终生成镜像，移除 Double Sided、Depth Axis、全局 Smooth、Boundary Smooth 及其配套输入。
- Fill Smooth 只平滑生成的侧壁，默认 2；Cutout 保持 Balloon / Shell 两种模式及其自身平滑控制。
- 两种深度 Cutout 入口均使用 Object Space 法线贴图，并开启材质 `O Image Layer` 的 Object Space。
- Shell 的 Normal Smooth 独立于厚度与参考深度的比例，实际控制壳体厚度偏移方向的平滑。

## Capabilities

### New Capabilities

- `post-cutout-symmetry`: 对已成形几何执行方向对齐、镜像、补面和补面平滑，定义原入口的节点串联及零厚度一致性。
- `shell-normal-smoothing`: 定义薄 Shell 的法线平滑作用及零厚度行为。

### Modified Capabilities

无。当前主规格目录为空；本变更接续 `add-projected-depth-symmetry` 中的节点实现。

## Impact

影响 `tools/nodes/groups/image_cutout_symmetry.py`、`image_depth_cutout.py`、相关共用节点函数、Cutout 对象创建与参数初始化、相关测试及 `src/anyimage/assets/O_AnyImage.blend`。不增加依赖。既有 `.blend` 内嵌节点不会自动迁移，后续从资产加载使用新接口。
