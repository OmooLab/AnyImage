## Why

`O Image Depth Plane` 与 `O Image Depth Panorama` 上由 Depth Mask 删点形成的切口，深度仍取该点自己的纹理采样；同一场景里 `O Image Depth Cutout` 的轮廓点和 Depth Split 切边早已改为取相邻面的采样。同类切口因此落在不同深度，clamp 或跨深度断裂的像素会把切口顶出尖刺。

## What Changes

- `build_surface_camera` 内建切口规则：自由边界点与 Depth Split 切边一样，深度取相邻面的采样，射线方向不变；删除仅有单一调用方使用的 `always_vertex` 参数。
- `O Image Depth Plane` 的原画幅外框与 mask 切口同规则：所有自由边界点都取相邻面采样，切口规则不带例外，外框也不再保留自身采样。
- `O Image Depth Panorama` 不传排除项：球面闭合，删除后出现的自由边界只有 mask 切口。
- Depth Mask 的删除由点改为面：面中心的采样低于阈值才删除该面，切口因此不再比阈值轮廓多退一圈，残留边也不需要单独清理。
- `O Image Depth Panorama` 去掉 `Invalid Distance`，无效判定只剩 mask 那一处；Depth Mask 关闭时保留的无效面落到 `Dome Radius`，它同时是 Depth Scale 为 0 时的球半径。
- `build_surface_camera` 不再接受排除字段：切口规则覆盖全部自由边界点，取消上一版「外框例外」。
- 平滑顺序保持不变：切口先取面深，切口带的深度模糊与位置平滑照常在其后作用。
- 重建 `O_AnyImage.blend`，补齐切口面深与实位不变的断言。

## Capabilities

### New Capabilities

- `mask-cut-depth-sampling`: Depth Plane 与 Panorama 上由 Depth Mask 删除产生的切口如何确定深度，以及原画幅外框的例外。

### Modified Capabilities

无。`openspec/specs` 尚无可修改的已归档规格。

## Impact

- `tools/nodes/common/depth_surface.py`：切口边界内建在 `build_surface_camera`，`always_vertex` 参数移除。
- `tools/nodes/groups/image_depth_plane.py`、`tools/nodes/groups/image_depth_panorama.py`：接入切口规则，Plane 额外声明原画幅外框。
- `tests/tools/nodes/`：切口面深断言，以及既有「Depth Mask 只删点、不改位置」断言的重写。
- `src/anyimage/assets/O_AnyImage.blend`：重新构建节点资产。
- 不改动 `O Image Depth Cutout`、`O Image Relief Plane`、Cutout 创建入口、材质与依赖。
