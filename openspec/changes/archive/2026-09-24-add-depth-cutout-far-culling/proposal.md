## Why

Depth Cutout 会保留选区内所有有效深度，即使远处深度明显脱离主体，也会生成被拉长或悬空的几何。需要一个基于最终物体空间位置的远端裁切，让用户能直接用 Blender 场景距离限制主体后方的几何范围。

## What Changes

- 为 `O Image Depth Cutout` 增加可见的 `Depth Limit` 距离输入。
- 以面中心深度判定超过限制的面，并把保留面与删除面的交界并入 Depth Split 的切边处理。
- 让 Depth Limit 边共用 Depth Split 的边界平滑、厚度 profile 修正、法线与闭合流程。
- 让裁切基于已经应用 `Reference Depth`、`Uniform Scale` 与 `Depth Scale` 的位置，因此调整这些参数时裁切结果同步更新。
- 创建 Depth Solid 与 Depth Symmetry 时，根据当前选区的有效深度中位数初始化裁切距离，默认使用中位深度的 1.2 倍作为相机深度上限并换算到对象空间。
- 补充节点接口、对象创建、几何行为和资产验证测试。

## Capabilities

### New Capabilities

- `depth-cutout-far-culling`: 定义 Depth Cutout 远端裁切的公开控制、物体空间语义、执行顺序与创建默认值。

### Modified Capabilities

无。

## Impact

影响 `src/anyimage/common/depth.py`、Cutout 对象创建、`nodes/groups/image_depth_cutout.py`、相关测试和生成的 `src/anyimage/assets/O_AnyImage.blend`。不增加依赖；节点组公开接口新增一个输入，既有 `.blend` 内嵌旧节点组不会自动获得该控制。
