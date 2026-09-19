## Why

`O Image Depth Panorama` 现在用 Delete Geometry 删除低 mask 面：接口只能给出「删除」，被删区域无法再作为几何参与后续处理，Depth Mask 关闭时也只能让无效面勉强落在 Dome Radius。改用 Separate Geometry 把两个区域分成独立分支，关闭开关时各走各的位移，再合并回一个输出。

## What Changes

- 低 mask 判定改为 Separate Geometry（Face 域）：`Selection` 输出低于 Mask Threshold 的面，`Invert` 输出其余面，取消 `O Image Depth Panorama` 对 Delete Geometry 的依赖。
- Depth Mask 打开时只走 `Invert` 分支：保持当前的排除行为，低 mask 区域不进入输出。
- Depth Mask 关闭时两个分支分别处理：低 mask 区域整片位移到 `Dome Radius` 球面，高 mask 区域照原路径做 Depth Split、径向深度与边界平滑，两者都在自身边界带上按 Boundary Smooth 松弛，最后 Join Geometry 合并输出。
- Depth Scale 为 0 且 Depth Mask 关闭时旁路全部分支：输出直接是 `Dome Radius` 的完整球面，不做分面、切分与平滑。
- 两个分支各自输出独立的网格，接缝点不再共享；输出几何为各分支结果的并集，取消关闭开关时 `O Image Depth Panorama` 的「逐位不变」契约。
- 重建 `O_AnyImage.blend`，并按分支语义重写既有全景断言。

## Capabilities

### New Capabilities

- `panorama-mask-regions`: `O Image Depth Panorama` 如何用 Mask Threshold 分出面区域、Depth Mask 开关如何选择分支，以及关闭时两个区域各自的位移与合并结果。

### Modified Capabilities

无。`openspec/specs` 尚无可修改的已归档规格。

## Impact

- `tools/nodes/groups/image_depth_panorama.py`：Separate Geometry 分面、双分支位移、Join Geometry 合并，不再调用 `validity.delete_invalid_faces`（该函数仍由 `O Image Depth Plane` 使用）。
- `tests/tools/nodes/test_image_depth_panorama.py`：Mask Threshold 分面、开关分支选择、Dome Radius 位移与合并结果的断言。
- `src/anyimage/assets/O_AnyImage.blend`：重新构建节点资产。
- 不改动 `O Image Depth Plane`、`O Image Depth Cutout`、`O Image Relief Plane`、Operator 入口、材质与依赖。
