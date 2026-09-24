## MODIFIED Requirements

### Requirement: Image Edit group uses Frame Mask and Rectify
系统 SHALL 将图片编辑工具组依次注册为 **Cutout**、**Frame**、**Mask** 和 **Rectify**，四个 WorkspaceTool SHALL 共用一个 3D Viewport 工具栏组。系统 MUST NOT 注册旧 Crop Lasso、Crop Polyline 或 Crop Perspective Tool ID，也 MUST NOT 提供旧 ID 的兼容入口。

#### Scenario: Image Edit tools are registered
- **WHEN** AnyImage 扩展完成注册
- **THEN** 3D Viewport 的同一图片编辑工具组按 Cutout、Frame、Mask、Rectify 顺序显示

#### Scenario: Legacy Crop tools are absent
- **WHEN** 系统枚举已注册的 AnyImage WorkspaceTool 和 Operator
- **THEN** 不存在 Crop Lasso、Crop Polyline、Crop Perspective 或其旧 ID

## ADDED Requirements

### Requirement: Image Empty context menu activates image tools
系统 SHALL 在 3D View 的 Image Empty `AnyImage` 右键菜单顶部按 Cutout、Frame、Mask、Rectify 顺序提供 WorkspaceTool 激活项。Cutout SHALL 以分隔线与其余三个 Tool 分开。每个菜单项 MUST 通过 AnyImage Operator 转调 `wm.tool_set_by_id` 激活对应 Tool，并 MUST NOT 直接调用关联的手势 Operator。

#### Scenario: Activate a tool from an Image Empty
- **WHEN** 用户在 3D View 中右键 Image Empty，并从 AnyImage 菜单选择 Frame、Mask、Rectify 或 Cutout
- **THEN** 对应 WorkspaceTool 成为当前 Tool，系统不立即提交图片编辑或 Shape 生成

#### Scenario: Continue editing with the activated tool
- **WHEN** 用户从右键菜单激活一个图片编辑 Tool 并完成一次有效手势
- **THEN** 该 Tool 保持激活，用户可以继续执行下一次手势

#### Scenario: Open AnyImage outside the 3D View
- **WHEN** 用户从 Outliner 的 Image Empty 菜单或 Shader Editor 的 AnyImage 菜单进入
- **THEN** 菜单不显示 Frame、Mask、Rectify、Cutout 的 WorkspaceTool 激活项

### Requirement: Image tools add no keyboard shortcut
系统 MUST NOT 为 Frame、Mask、Rectify 或 Cutout 新增扩展级激活快捷键。

#### Scenario: Inspect extension keymaps
- **WHEN** 检查 AnyImage 注册的扩展级 keymap item
- **THEN** 不存在用于激活四个图片编辑 WorkspaceTool 的新绑定
