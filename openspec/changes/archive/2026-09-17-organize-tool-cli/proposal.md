## Why

节点组和模型工具需要统一为「对象 + 动作」命令，让构建、检查、预览和模型准备的职责直观可见，并能独立执行。

## What Changes

- **BREAKING**：将 `build-nodes` 替换为 `node-group build`，将 `sync-models` 替换为 `model sync`，删除旧入口。
- 提供 `node-group check`，检查已有资产并运行测试；提供 `node-group preview`，生成当前源码的 HTML 预览并打开浏览器。
- 提供 `model prepare`，按模型来源下载现成文件或准备源权重并导出，统一校验全部模型。
- 使用统一的小写子命令；未提供动作时显示帮助。

## Capabilities

### New Capabilities

- `developer-tool-cli`：节点组和模型命令的路由、执行边界、参数及失败行为。

### Modified Capabilities

无。

## Impact

涉及 `pyproject.toml` 的脚本入口、`tools/nodes`、`tools/models` 和相关命令测试。使用现有 argparse、Blender 与模型转换依赖。实施范围为命令代码与测试；本次产出为 OpenSpec 规划文件。
