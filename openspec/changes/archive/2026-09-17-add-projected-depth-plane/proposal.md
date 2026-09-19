## Why

整图相机投影曲面需要与普通 Plane 一样稳定的矩形基础网格，以及少量直接的深度控制。将它作为独立转换入口，也让 Cutout 的交互集中在用户圈选区域。

## What Changes

- **BREAKING**：完全删除 Cutout 双击整图生成入口，包括快捷键、`full_image` 属性和整图 Selection 构造分支。
- 新增 **Convert to Depth Surface**，与 Convert to Plane、Convert to Depth Plane 并列，用完整图片生成相机投影深度曲面。
- 新增 `O Image Depth Surface`：基础网格复用普通 Plane 的矩形、UV、中心原点和 `O Mesh Plane` 细分，只公开 `Subdivide`、`Thickness`、`Depth Scale`、`Reference Depth` 四项用户参数。
- 相机投影沿用 Depth Cutout 的坐标与深度缩放语义；厚度采用均匀曲面壳，默认零厚度。
- 整图转换复用现有 MoGe-2 单次推理、材质与对象替换流程。

## Capabilities

### New Capabilities

- `projected-depth-surface`: 整图 Depth Surface 转换、矩形基础网格、相机投影和精简节点接口。
- `cutout-lasso-entry`: Cutout 通过有效套索进入 Shape 选择，彻底移除双击整图入口。

### Modified Capabilities

无。当前 `openspec/specs/` 尚无已归档规范；本次独立规定新增及调整后的行为。

## Impact

- `operators/cutout_tool/main.py` 及其交互测试。
- `operators/convert_to_plane/`、`menu.py`、`__init__.py` 的转换入口、结果创建与类型注册。
- `common/depth.py` 等共用深度数据处理；按需扩展整图 Job 的产物选择，保持后端模块边界。
- `tools/node_assets/` 的构建和验证、新节点组及节点测试；实施阶段按项目约束执行测试，节点资产构建和产物更新单独安排。
- 无新增第三方依赖；实现以当前工作区为基线，衔接正在进行的 Cutout Shape 调整。
