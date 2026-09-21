## Why

Frame、Mask、Rectify、Cutout 只作用于 Image Empty，但当前主要入口位于整个 Object Mode 都可见的 3D View 工具栏，缺少与目标对象直接关联的快速入口。将它们加入 Image Empty 右键菜单可以提升指向性，同时保留 WorkspaceTool 的连续编辑能力。

## What Changes

- 在 3D View 的 Image Empty `AnyImage` 右键菜单顶部按 Cutout、Frame、Mask、Rectify 顺序增加四个工具入口，并以分隔线突出 Cutout。
- 菜单项通过轻量 AnyImage Operator 调用 `wm.tool_set_by_id` 激活对应 WorkspaceTool，不直接执行一次性手势 Operator。
- 激活后工具保持当前状态，用户可连续执行多次图片编辑。
- 保留现有 WorkspaceTool 工具栏入口，并将四个工具按 Cutout、Frame、Mask、Rectify 顺序合并为一个工具组。
- Outliner 和 Shader Editor 菜单不显示 WorkspaceTool 激活项，避免在非 3D View 区域调用工具切换。
- 暂不增加任何键盘快捷键。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `image-edit-tools`: 四个图片编辑 WorkspaceTool 统一组成一个工具栏组，并可从 3D View 的 Image Empty 右键菜单激活。

## Impact

- 主要影响 `src/anyimage/menu.py`、`src/anyimage/tools.py` 及菜单和注册测试。
- Frame、Mask、Rectify、Cutout 的 Operator、Tool ID、行为和设置保持不变。
- 不新增快捷键、依赖、兼容入口或一次性 Cutout 执行路径。
