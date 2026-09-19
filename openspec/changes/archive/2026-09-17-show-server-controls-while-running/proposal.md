## Why

Server 处于 Busy 时仍然是 Running，但当前面板会隐藏重启和停止按钮，导致用户在任务执行期间无法直接管理 Server 生命周期。Running 的控制入口应保持一致，不应受 Busy、等待或其他运行中子状态影响。

## What Changes

- Server 只要处于 Running，就显示重启和停止按钮。
- Busy、等待及其他运行中子状态继续显示各自的状态信息，但不再隐藏生命周期控制按钮。
- Cached 列表包含多个模型时，每个模型换行显示，避免单行内容过长。
- 补充 UI 测试，覆盖运行中状态的按钮可见性与 Cached 列表布局。

## Capabilities

### New Capabilities

- `server-lifecycle-controls`: 规定 Server 在所有 Running 子状态下提供一致的重启与停止入口。
- `server-cache-display`: 规定 Server 面板中 Cached 模型列表的分行展示行为。

### Modified Capabilities

无。

## Impact

- `src/anyimage/panel.py` 中 Server 状态与控制按钮的展示逻辑。
- Blender Add-on UI 测试。
- 不改变 Server API、状态协议或依赖。
