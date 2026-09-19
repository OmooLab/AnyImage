## Why

现有图片编辑入口分散为四个 Image Selection Tool 和一个独立 Perspective Tool，其中 Line 与 Polyline 功能重叠，工具名称也没有直接表达裁切产物；同时编辑选项缺少稳定状态，Cutout 的局部向内轴还与源 Image Empty 不一致。将图片裁切工具收拢为一个明确的 Crop Tool 组，并统一持久选项与坐标约定，可以减少工具栏占用和后续编辑歧义。

## What Changes

- **BREAKING**：将 Image Box、Image Lasso、Image Polyline 与 Image Perspective 重命名并重组为同一个四合一 **Crop Tool** 工具组，子工具依次命名为 **Crop Box**、**Crop Lasso**、**Crop Polyline**、**Crop Perspective**。
- **BREAKING**：删除 Image Line WorkSpaceTool、对应半平面手势分支、公开 Tool ID、源码入口、测试与文档，不保留兼容入口。
- **BREAKING**：将原 `image_tool/` 与 `perspective_tool/` 的用户概念、Tool ID、Operator 名称和源码边界统一迁移为 `crop_tool/` 与 Crop 术语，不保留旧名称转发。
- 将 Crop Tool 注册为一个工具栏组，并让使用 Add UV Sphere 图标的 Cutout Tool 作为第二个独立工具栏入口紧接在该组之后；两个工具之间不显示分割线。
- 为 Crop Box、Crop Lasso 与 Crop Polyline 增加彼此独立保存的 **Invert** 工具选项，默认关闭；Crop Perspective 不提供 Invert，Crop Tool 不为选项注册字母快捷键。
- 为四个 Crop 子工具增加彼此独立保存的 **Keep Original** 工具选项，默认关闭；开启后每次裁切创建并激活结果 Image Empty，同时保留但不继续选择源 Image Empty。
- 为 Cutout 增加 **Inward Axis** 工具选项，可选择 `-Z` 或 `+X`；默认 `-Z`，使生成 Mesh 的局部坐标方向与源 Image Empty 一致，`+X` 保留当前 Cutout 坐标约定。
- 让 Cutout 的四种 Shape、Depth 几何与 Object Space Normal Map 统一遵循所选 Inward Axis，同时保持世界空间图片位置和正反面语义不变。
- 同步菜单、工具提示、状态栏、节点资产、测试、README 与内部文档。

## Capabilities

### New Capabilities

- `crop-tool-options`: 规定四合一 Crop Tool 的组成、命名、注册顺序、独立 Keep Original、适用子工具的独立 Invert，以及 Cutout 的相邻位置和 Inward Axis 坐标约定。

### Modified Capabilities

无。

## Impact

- 影响 `operators/image_tool/`、`operators/perspective_tool/`、共享 Viewport 手势、Scene 工具设置、菜单与扩展注册；实现迁移到统一的 `operators/crop_tool/` 边界。
- 旧 Image Tool / Perspective Tool 的 Tool ID、Operator ID、类名、模块路径和 Image Line 行为不再可用。
- Crop Selection 的本地与 Refine Selection 异步结果路径、Crop Perspective 的本地结果路径都需要支持保留源对象，并选择、激活结果对象。
- Cutout 的对象矩阵、统一 Geometry Nodes 资产和 Object Space Normal 转换需要接受所选 Inward Axis；本地与异步 Shape 路径必须传递同一选项。
- 需要更新 Blender 注册、交互、裁切、Cutout 对象与节点资产测试，以及用户文档、Crop Tool、Cutout 和节点资产内部文档。
- 不新增依赖，不改变 Cutout 的 Selection 栅格化或 AI Job 输入产物协议；删除其临时 `F` Invert 交互。
