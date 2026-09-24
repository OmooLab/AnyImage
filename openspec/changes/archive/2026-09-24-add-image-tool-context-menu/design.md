## Context

AnyImage 的 Frame、Mask、Rectify、Cutout 都是 Object Mode WorkspaceTool，并且只对 Image Empty 有效。四个 Tool 当前从工具栏进入，其中前三个属于一个组，Cutout 单独占用一个工具栏槽位。Image Empty 已有 `AnyImage` 右键子菜单，但其中只有转换、Remove Background、Upscale 和设置操作。

WorkspaceTool 适合连续编辑：每次手势由关联 Operator 完成，Tool 在操作结束后仍保持激活。右键菜单应当成为上下文明确的 Tool 激活入口，而不是增加一套一次性 Operator 执行模式。

## Goals / Non-Goals

**Goals:**

- 从 3D View 的 Image Empty 右键菜单快速激活四个图片编辑 Tool。
- 激活后保留 WorkspaceTool 的连续编辑语义。
- 将四个 Tool 按 Cutout、Frame、Mask、Rectify 顺序合并为一个工具栏组，降低全局工具栏占用。
- 在菜单中显式声明需要提供的 Tool 及其顺序，方便入口独立演进。

**Non-Goals:**

- 不移除 WorkspaceTool 或工具栏入口。
- 不从菜单直接调用 Frame、Mask、Rectify、Cutout 的手势 Operator。
- 不增加快捷键、切换回上一个 Tool 的行为或一次性执行模式。
- 不在 Outliner、Shader Editor 或非 Image Empty 上显示 Tool 激活项。

## Decisions

### 1. 菜单通过普通 AnyImage Operator 激活 Tool

`AnyImageImageMenu.draw()` 显式添加 Cutout、Frame、Mask、Rectify 四个 `anyimage.activate_workspace_tool` 菜单项，并将 `tool_id` 设置为对应 Tool 的 `bl_idname`。菜单项直接引用 Tool 类型的标签和标识，但不遍历完整 Tool 注册清单，使菜单可以独立决定未来显示哪些 Tool。Tool 项位于菜单顶部，Cutout 后插入分隔线，不设置与工具栏图标不一致的菜单图标。

`wm.tool_set_by_id` 会被 Blender 识别为 Tool 按钮，并使用比普通 Operator 更宽的 toolbar icon 占位，导致菜单文字无法与其他操作对齐。`ActivateWorkspaceTool` 只负责在执行阶段转调 `wm.tool_set_by_id`；菜单按钮本身保持普通 Operator 布局。

选择激活 WorkspaceTool 而不是直接执行关联 Operator，原因是现有手势 Operator 会检查 active Tool，并以 Viewport 鼠标事件作为选择起点。菜单点击事件不适合作为手势起点，而且一次性 Operator 会失去连续编辑能力。

### 2. 只在 3D View 的 Image Empty 菜单显示

现有 `AnyImageImageMenu` 同时被 3D View 和 Outliner 使用。绘制 Tool 项目前检查 `context.area.type == "VIEW_3D"`：

- 3D View 中右键 Image Empty：在菜单顶部显示 Cutout、分隔线、Frame、Mask、Rectify。
- Outliner 中右键 Image Empty：继续显示现有操作，不显示 Tool 激活项。
- Shader Editor：使用独立菜单，不受影响。

Tool 菜单项使用 `EXEC_DEFAULT`；现有图片操作继续使用 `INVOKE_DEFAULT`。

### 3. 四个 Tool 共用一个工具栏组

`tools.TOOLS` 使用 Cutout、Frame、Mask、Rectify 顺序。Cutout 以 `group=True` 建立工具组，其余三个 Tool 依次使用 `after` 和 `separator=False` 加入同一组。注册与逆序注销机制不变。

保留工具栏组是因为注册的 WorkspaceTool 需要工具栏承载当前模式和设置；右键菜单作为主要上下文入口，工具栏组作为当前 Tool 的可见状态和备用切换入口。

### 4. 测试覆盖用户可见入口

扩展注册测试更新 Cutout 的注册参数并继续验证顺序与清理。菜单测试验证：

- 3D View Image Empty 菜单包含四个 `wm.tool_set_by_id` 项，顺序和 Tool ID 正确。
- Outliner/非 3D View 菜单不包含这些项。
- 现有转换和图片操作仍然存在。

不新增对 Blender 内部工具组渲染细节的脆弱断言；通过注册参数验证分组关系。

## Risks / Trade-offs

- [Outliner 调用 Tool 切换缺少 3D View 上下文] → 按 area type 限制 Tool 菜单项只在 3D View 显示。
- [菜单与工具栏顺序可能不同] → 菜单显式声明其入口，这是允许独立调整的界面顺序。
- [Cutout 分组参数在 Blender 版本间表现不同] → 保持与现有三个 Tool 相同的连续 `after` 和 `separator=False` 注册方式。
