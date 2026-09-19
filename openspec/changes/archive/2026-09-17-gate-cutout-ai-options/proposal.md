## Why

Cutout 的 AI 依赖目前只在 `Fit to Foreground` 附近提示，无法覆盖 `Generate Normal Map` 和两个 Depth shape，用户可能在选择后才发现环境不可用。Image Box 与 Image Lasso 的同类入口位置也不一致，需要统一为可预期的工具设置体验。

## What Changes

- AI 环境未就绪时，在 Cutout、Image Box 和 Image Lasso 的工具设置开头显示 AI 环境设置按钮。
- AI 环境未就绪时，禁用 `Fit to Foreground`；Cutout 同时禁用 `Generate Normal Map`。
- AI 环境未就绪时，Cutout shape 菜单只显示不依赖 AI 的 `Surface` 和 `Balloon`；环境就绪后显示包含两个 Depth 模式的四个 shape。
- Cutout 读取设置时忽略 AI 环境未就绪状态下遗留的 AI 选项值，确保本地 shape 不触发 AI job。

## Capabilities

### New Capabilities

- `image-tool-ai-availability`: 定义 Cutout、Image Box 和 Image Lasso 根据 AI 环境可用性呈现设置与可执行模式的行为。

### Modified Capabilities

无。

## Impact

- 影响 Blender View3D 工具设置绘制与区域工具共享交互逻辑。
- 影响 Cutout shape pie 的候选项与设置值传递。
- 不新增依赖，不改变服务器协议、节点资产或已有 shape 实现。
