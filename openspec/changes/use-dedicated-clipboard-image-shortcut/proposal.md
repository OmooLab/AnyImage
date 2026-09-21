## Why

AnyImage 目前拦截 `Ctrl/Cmd+C` 与 `Ctrl/Cmd+V`，依靠单个 Blender 进程内的剪贴板序列号判断是否交回原生粘贴；跨 Blender 实例复制对象或节点时，该状态无法共享，可能把系统剪贴板中的旧图片误粘贴到场景。图片粘贴应使用独立快捷键，使 Blender 原生复制粘贴始终保持完整行为。

## What Changes

- **BREAKING**：将图片粘贴快捷键从 `Ctrl/Cmd+V` 改为 `Shift+Ctrl/Cmd+V`。
- 删除 AnyImage 的 `Ctrl/Cmd+C` 绑定、原生复制跟踪 Operator、进程内 token 与平台剪贴板变更序列判断。
- 将 3D View 图片粘贴限制在实际支持的 Object Mode 与画笔纹理模式；Pose、Grease Pencil 及其他不支持模式继续使用 Blender 自身的 `Shift+Ctrl/Cmd+V`。
- 保留 Node Editor 中受支持节点树的图片粘贴，并让不支持的上下文继续交由 Blender 处理。

## Capabilities

### New Capabilities

- `clipboard-image-shortcut`: 定义独立图片粘贴快捷键、支持上下文及与 Blender 原生复制粘贴的边界。

### Modified Capabilities


## Impact

- `src/anyimage/keymaps.py`：只注册独立图片粘贴快捷键。
- `src/anyimage/operators/clipboard_image/operators.py`：删除复制跟踪状态与 Operator，收紧粘贴可用上下文。
- `src/anyimage/operators/clipboard_image/clipboard.py`：删除仅供原生复制跟踪使用的剪贴板 token 读取。
- `src/anyimage/operators/clipboard_image/__init__.py`、`src/anyimage/__init__.py`：移除跟踪 Operator 的导出与注册。
- 相关快捷键、注册与模式分流测试随实现更新；不新增依赖，不修改图片读取、缓存或落点行为。
