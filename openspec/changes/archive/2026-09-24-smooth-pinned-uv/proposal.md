## Why

`pinned_smooth` 目前只松弛顶点位置并原样保留 UV，导致边界、切缝或填充衔接带变平滑后，纹理坐标仍保持原来的阶梯形状，产生可见的纹理锯齿与几何轮廓错位。共享平滑需要把 UV 视为随表面形变传递的坐标，同时保护 UV seam 与 island 边界。

## What Changes

- 修改共享 `pinned_smooth` 语义，使其在迭代松弛 Position 时同步松弛已有的 `UVMap`。
- 对 Position 与 UV 使用相同的迭代次数、作用范围、权重和 pin 规则；作用范围外及零迭代时两者均保持不变。
- 保持 UV 的 Face Corner 语义，禁止跨 UV seam 或 UV island 混合；`pinned_smooth` 默认输入几何具有 `UVMap`。
- 让 Depth Cutout、Depth Plane、Depth Panorama 与 Cutout Symmetry 的既有 `pinned_smooth` 调用自动获得统一行为，不调整其他深度、法线、属性或着色 Smooth。
- 更新节点行为测试与资产验证，覆盖 UV 随动、范围隔离和 seam 保持。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `pinned-geometry-smoothing`: 共享 pinned smoothing 从仅松弛顶点位置改为同步松弛表面 UV，并规定 UV seam、UV island、作用范围及缺失属性的行为。

## Impact

影响 `nodes/common/smoothing.py`、调用 `pinned_smooth` 的边界与对称节点组行为、相关 `tests/nodes/` 测试，以及重新生成的 `src/anyimage/assets/O_AnyImage.blend`。不新增公开输入、依赖或兼容层；不改变未使用 `pinned_smooth` 的 Smooth 行为。
