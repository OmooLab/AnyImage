## Why

Depth Split 现在的判据只由深度采样差和局部采样密度决定，Depth Scale 完全不参与。于是 Depth Scale 为 0（表面被压成完全平的一层）时仍然切开并删除条带面，平面上留下没有几何依据的缝隙。用户把 Depth Scale 理解为显示幅度，0 应当不产生任何切割。

## What Changes

- Depth Split 的比较式乘上 Depth Scale，判据从「源深度数据的断层」改为「投影后表面的几何落差」。
- Depth Scale 为 0 时不切开、不删除条带面，也不改变拓扑；Depth Scale 增大时切边逐步出现。
- 三个使用该判据的资产行为一致：`O Image Depth Plane`、`O Image Depth Cutout`、`O Image Depth Panorama`。
- 默认 Depth Scale 为 1，默认行为与现在完全相同。**BREAKING**：Depth Scale 由纯显示参数变为影响拓扑的参数，保存了 Depth Scale 小于 1 的场景会看到切边减少、顶点数与壳壁结果随之改变。
- 同步修订 `reorganize-cutout-shapes` 中「Split 独立于显示深度幅度」的过时条目。

## Capabilities

### New Capabilities

- `depth-split-selection`: Depth Split 依据什么判定相邻面之间的断层，以及 Depth Scale 在其中的作用。

### Modified Capabilities

无。`openspec/specs` 尚无可修改的已归档规格。

## Impact

- `tools/nodes/common/depth_surface.py`：`split_depth_surface` 增加 Depth Scale 输入，比较式乘该因子。
- `tools/nodes/groups/image_depth_plane.py`、`image_depth_cutout.py`、`image_depth_panorama.py`：传入各自的 Depth Scale。
- `tests/tools/nodes/test_depth_surface_split.py`：反转「Depth Scale 不改变切边」的断言，补充 Depth Scale 0 不切开的覆盖。
- `src/anyimage/assets/O_AnyImage.blend`：重新构建节点资产。
- 不改动 `O Image Relief Plane`、Cutout 创建入口、材质与依赖。
