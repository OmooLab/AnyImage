## Context

AnyImage 当前在 3D View 与 Node Editor 注册 `Ctrl/Cmd+C` 和 `Ctrl/Cmd+V`。复制跟踪 Operator 保存当前进程看到的 Windows 剪贴板序列号，粘贴 Operator 据此决定接管图片还是返回 `PASS_THROUGH`。Blender 的对象与节点复制可以跨实例，而该 Python 状态不能，且 macOS/Linux 没有对应 token 实现，因此同一快捷键无法可靠表达两种粘贴意图。

Blender 默认 keymap 已在 Pose 与 Grease Pencil 等模式使用 `Shift+Ctrl/Cmd+V`。AnyImage 的 3D View 目标判断目前对所有非画笔模式返回 Plane，单纯替换按键仍会抢占这些原生行为。

## Goals / Non-Goals

**Goals:**

- 使用独立快捷键触发剪贴板图片粘贴。
- 完全停止监听原生复制快捷键，使跨实例与同实例的 Blender Copy/Paste 行为一致。
- 只在 AnyImage 实际支持的上下文中响应独立快捷键，其他模式由 Blender 或其他 keymap item 继续处理。
- 删除不再需要的复制跟踪状态、平台 token 和测试。

**Non-Goals:**

- 不自动判断用户最后复制的是 Blender 数据还是系统图片。
- 不改变系统剪贴板图片格式读取、Packed Image 缓存、落点或表示形式。
- 不处理用户自定义 keymap 或其他扩展造成的任意快捷键冲突。
- 不为旧快捷键或复制跟踪入口保留兼容层。

## Decisions

### 1. 图片粘贴使用独立主修饰键组合

`PasteClipboardImage` 在 Windows/Linux 使用 `Shift+Ctrl+V`，在 macOS 使用 `Shift+Cmd+V`。`Ctrl/Cmd+V` 和 `Ctrl/Cmd+C` 均不再由 AnyImage 注册。

独立快捷键让操作意图由用户输入直接表达，无需推断两个相互独立的剪贴板中哪一个更新得更晚。备选的跨进程 token 文件仍依赖平台剪贴板版本能力，并增加会话过期、并发与异常清理问题，因此不采用。

### 2. 上下文判断负责避让原生快捷键

3D View 仅在 Object Mode 返回 `PLANE`，在 `SCULPT`、`PAINT_TEXTURE`、`PAINT_VERTEX` 返回 `TOOL_TEXTURE`；其他模式返回 `None`。Node Editor 继续只接受当前列出的 Shader、Compositor 与 Geometry 节点树。

`PasteClipboardImage.poll()` 继续以 `target_for_context()` 为唯一业务可用性入口。这样 Pose 和 Grease Pencil 等模式中的 Operator poll 失败，Blender 可继续匹配自身的 `Shift+Ctrl/Cmd+V`。不在 keymap 注册器内增加模式分支，保持注册层只描述静态绑定。

### 3. 删除复制跟踪链而非留空

删除 `TrackNativeCopy`、`_native_copy_token`、`_should_defer_to_native_paste()` 与 `clipboard_change_token()`，同时移除导出、注册项和相关测试。`PasteClipboardImage` 收到有效调用后直接读取图片；没有图片时仍返回 `PASS_THROUGH`。

这符合项目不保留旧路径和兼容层的约束，并使 macOS、Linux、Windows 共用同一控制流。

### 4. 测试覆盖用户可见边界

快捷键测试验证每个目标编辑器只注册一个带 Shift 的平台主修饰键组合，并确认没有 Copy 绑定。上下文测试增加 Pose、Grease Pencil 与普通编辑模式不可用的断言，同时保留 Object、画笔模式和受支持节点树覆盖。粘贴执行测试不再模拟复制 token。

## Risks / Trade-offs

- [用户已习惯直接按 `Ctrl/Cmd+V` 粘贴图片] → 这是明确的快捷键迁移，通过快捷键测试固定新组合；本次按项目规范不主动同步说明文档。
- [Pose 或 Grease Pencil 的原生组合仍被扩展 keymap 匹配] → 通过 Operator `poll()` 的严格模式边界使 AnyImage 在这些上下文不可执行。
- [用户自定义 keymap 或其他扩展占用相同组合] → 使用 Blender 标准 addon keymap 注册，允许用户在 Preferences 中查看和调整；不引入运行时冲突仲裁。
- [收紧 3D View 模式遗漏现有有效路径] → 以当前 `BRUSH_TEXTURE_MODES` 和 Plane 的 Object Mode 前置条件为准增加针对性测试。
