## Why

`O_AnyImage.blend` 可以由 Python 节点定义完整重建，却长期作为 Git LFS 资产提交，每次更新都会累积新的二进制历史。与此同时，节点组业务定义与构建、校验、预览工具都位于 `tools/nodes`，源码边界没有体现“节点组”和“节点构建工具”的区别。

## What Changes

- 将 `tools/nodes/groups` 和 `tools/nodes/common` 移至根目录 `nodes/groups` 和 `nodes/common`，作为节点组及其共用构建定义。
- `tools/nodes` 仅保留构建入口、资产校验、布局和预览等开发工具。
- 更新源码、测试、打包配置和工具入口中的导入路径，不保留旧路径兼容层。
- `node-group` 统一使用 `blender` dependency group 提供的 `bpy` wheel，不再查找或启动本地 Blender 应用程序。
- 删除 `--blender` 参数、`BLENDER_BIN` 环境变量、项目 `.env` 读取及其相关测试和说明。
- **BREAKING**：`src/anyimage/assets/O_AnyImage.blend` 不再纳入 Git/LFS；干净源码检出必须先构建节点资产，才能直接加载扩展或打包。
- 测试 CI 和发布 CI 使用 `bpy` wheel 在运行测试或打包前生成并校验节点资产。
- 打包流程继续要求并包含生成后的 `O_AnyImage.blend`，缺少资产时明确失败。
- 更新节点资产内部文档和项目规范，使源码、构建产物及 CI 职责一致。

## Capabilities

### New Capabilities

- `generated-node-assets`: 定义节点资产从源码生成、在 CI 中验证并进入发布包的完整契约。

### Modified Capabilities

- `maintainable-project-structure`: 将节点组业务定义与节点资产开发工具拆分为 `nodes/` 和 `tools/nodes/` 两个职责边界。
- `developer-tool-cli`: 节点工具改为通过当前 uv Python 的 `bpy` wheel 构建、校验和预览，不再依赖外部 Blender 可执行程序。

## Impact

- 移动 `tools/nodes/groups`、`tools/nodes/common` 及其全部导入引用，并将根目录 `nodes` 纳入开发工具 wheel。
- 修改 `.github/workflows/test.yml`、`.github/workflows/release.yml`、节点工具测试和打包测试。
- 简化 `tools/nodes/cli.py`，删除 Blender 路径发现、`.env` 配置和外部 Blender bootstrap。
- 从版本控制移除 `src/anyimage/assets/O_AnyImage.blend`，更新 `.gitignore` 和 LFS 跟踪状态。
- 修改 `AGENTS.md` 与 `docs/internals/node-assets.md` 中关于节点资产提交和构建的规则。
- 不改变节点组名称、接口、求值行为或最终扩展包内容。
