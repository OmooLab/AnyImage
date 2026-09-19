## Why

现有 Crop Lasso 实际需要反复编辑图片 Alpha，却会紧裁切画布并把 Lasso、Polyline 分成独立工具；Crop Perspective 的名称也没有直接表达透视校正目的。将图片编辑入口收敛为简短的 **Frame / Mask / Rectify**，可以让工具名称、画布行为和用户操作保持一致。

## What Changes

- **BREAKING**：将 Crop Tool 组改为 **Frame / Mask / Rectify**，删除 Crop 命名和旧工具 ID，不保留兼容入口。
- **BREAKING**：删除 Crop Polyline；Mask 在一个 Tool 中提供 Lasso 与 Brush 两种手势。
- Mask 提供 Set、Add、Subtract 三种 Alpha 编辑模式；Brush 额外提供可持久保存的 Radius。
- Mask 始终保留当前图片的完整矩形画布、分辨率和 Image Empty 变换，只修改 Alpha，不再按可见内容紧裁切。
- 将 Crop Perspective 重命名为 **Rectify**，继续通过四点 Homography 生成透视校正结果。
- **BREAKING**：删除 Frame / Mask / Rectify 工具组中的 **Keep Original**，结果直接替换 active Image Empty 承载的图片。
- **BREAKING**：删除 Crop 与 Cutout 的 **Refine Selection** 选项、请求参数、Job 和结果处理；BEN2 继续用于 Remove Background 与调试。

## Capabilities

### New Capabilities

- `image-edit-tools`: 规定 Frame、Mask、Rectify 的工具组成、命名、Mask 手势与 Alpha 模式、稳定画布，以及结果替换行为。

### Modified Capabilities

无。

## Impact

- 影响 Crop 工具注册、激活入口、WorkspaceTool、公共 Viewport 手势、Scene 设置、图片结果落地和相关测试。
- 影响 Cutout 的工具设置、交互参数、Job 编排，以及 Server 的 Refine Selection Job 注册与文件。
- 影响 README、用户索引、内部架构、Operator、Runtime、Output 和公共模块文档。
- 不新增依赖，不改变 Frame 合成、Rectify Homography、Cutout Shape、Depth、Normal Map、Remove Background 或 BEN2 模型实现。
