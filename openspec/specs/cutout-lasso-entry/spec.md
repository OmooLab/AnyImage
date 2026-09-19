# cutout-lasso-entry Specification

## Purpose
TBD - created by archiving change add-projected-depth-plane. Update Purpose after archive.
## Requirements
### Requirement: Cutout starts shape generation from a lasso
Cutout SHALL 在用户提交有效套索后打开 Shape Pie Menu，并将圈选路径传给 Shape 生成入口。

#### Scenario: Submit a lasso
- **WHEN** 用户在 active Image Empty 上完成有效 Cutout 套索
- **THEN** 系统打开当前可用 Shape 菜单并传递该套索路径

### Requirement: Full-image double-click entry is removed
系统 MUST 删除 Cutout 的双击整图 keymap、`full_image` Property、整图 Selection 构造分支及专属调用代码。双击 MUST NOT 打开整图 Shape 菜单或提交整图生成任务。

#### Scenario: Double-click an image
- **WHEN** Cutout 已激活，用户在 Image Empty 上双击且未形成有效套索
- **THEN** 不打开 Shape 菜单、不创建对象、不提交生成 Job

#### Scenario: Double-click viewport space
- **WHEN** active Image Empty 存在，用户在图片外空白区域双击
- **THEN** 不启动整图 Cutout，选择处理沿用共享图片手势规则

#### Scenario: Inspect registration
- **WHEN** 检查 Cutout 的 Operator Property 和 WorkspaceTool keymap
- **THEN** 不存在 `full_image` 或用于整图生成的 `DOUBLE_CLICK` 绑定

