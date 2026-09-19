## Why

`O Image Cutout Symmetry` 在补面之前按「任一顶点越过对称面即删除整个面」切掉界外几何，保留区因此整体退让，退让量随局部深度梯度逐处不同。补面随后不得不把这条不共面的切口也连起来，生成的侧壁宽度逐边变化且平面着色，Fill Smooth 只柔化新增环的面内位置，无法消除宽度差；对称对象在中缝处出现一圈明显杂乱的面。

## What Changes

- 对称节点的切口统一为「把越过对称面的顶点折叠到对称面，删除整体贴平的面与内部贴平边」，使零厚度与非零厚度输入的切边落在同一位置。
- 补面只连接不落在对称面上的边界边。落在对称面上的切口由镜像后的合并直接焊成接缝，不再生成侧壁。
- 新增 `Seam Smooth` 并重定义 `Fill Smooth`：两者都只移动面内分量、锁定对称轴；`Seam Smooth` 按两圈渐变松弛切口环，`Fill Smooth` 按四圈渐变松弛 front 的衔接带，锚点为界外轮廓与对称面上的切缝，因此对称轴上的点同样参与。
- 补面细分始终存在，不再以 `Fill Smooth > 0` 为开关；`Fill Smooth` 平滑界外轮廓，侧壁从平滑后的轮廓构建。
- 不引入布尔、裁切算子、细分或新增采样参数。

## Capabilities

### New Capabilities

- `cutout-symmetry-seam`: 对称节点切口与补面的边界语义，包括切口落在对称面上、镜像自焊、补面只覆盖外轮廓，以及独立的切边平滑参数。

### Modified Capabilities

无。`openspec/specs` 尚无可修改的已归档规格，已完成的 `compose-depth-cutout-symmetry` 仍未归档。

## Impact

- `tools/nodes/groups/image_cutout_symmetry.py`：删除、吸附与补面选择。
- `tests/tools/nodes/test_cutout_symmetry.py`：切口位置、封闭性与属性断言。
- `src/anyimage/assets/O_AnyImage.blend`：重新构建节点资产。
- 不改动 `O Image Depth Cutout`、Cutout 创建入口、材质或依赖。
