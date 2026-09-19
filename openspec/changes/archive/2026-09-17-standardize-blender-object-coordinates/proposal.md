## Why

AnyImage 生成对象的局部坐标系仍沿用 Image Empty 的 `XY + depth -Z`，与 Blender 常规对象坐标 `up=Z`、`front=-Y` 不一致。Cutout 因此需要额外的 `Depth Axis` 来把结果转到左右轴，但没有真正解决对称轴、深度方向和 Object Space Normal 的耦合问题。

## What Changes

- 统一所有生成几何的 canonical local frame：X 为图片水平、Z 为图片 up、+Y 为图片纸内深度、front 为 -Y。
- BaseShape 与 Plane、Depth Plane、Relief Plane、Cutout、Depth Cutout 的未修改网格统一位于 XZ 平面，`Y=0`。
- **BREAKING**：删除 `O Image Cutout` 与 `O Image Depth Cutout` 的 `Depth Axis` 输入及最终轴向旋转逻辑。
- `O Image Cutout Symmetry` 在 canonical 坐标中沿 Y 轴镜像，最后绕 Z 旋转使对称轴指向 +X，并保持 up=+Z。
- Depth Symmetry 最终对象允许 front 从 -Y 改变为 -X，以换取左右对称轴为 X。
- Object Space Normal 的生成与着色转换随新 canonical frame 和最终对称朝向同步调整。

## Capabilities

### New Capabilities

- `canonical-object-frame`: 定义所有生成几何共用的 Blender 对象局部坐标系、BaseShape 平面、UV 映射与深度方向。
- `depth-symmetry-orientation`: 定义 Depth Symmetry 的 canonical 镜像轴、最终对称轴和 up 轴约束，以及允许 front 改变的最终朝向。
- `object-space-normal-alignment`: 定义 Object Space Normal 如何随 canonical frame、Depth Symmetry 镜像与最终朝向保持对齐。

### Modified Capabilities

无。当前 `openspec/specs/` 中没有既有 capability 规格。

## Impact

影响 `src/anyimage/operators/cutout_tool/geometry.py`、`object.py`、`depth_calibration.py`，`src/anyimage/operators/convert_to_plane/`，`tools/nodes/groups/` 下的 Plane、Depth Plane、Relief Plane、Cutout、Depth Cutout、Symmetry 与材质节点，`tools/nodes/common/` 的深度表面、Cutout 和法线映射辅助，以及相关测试与 `src/anyimage/assets/O_AnyImage.blend`。不新增依赖。
