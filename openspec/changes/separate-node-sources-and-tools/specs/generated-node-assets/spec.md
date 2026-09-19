## ADDED Requirements

### Requirement: Node asset is generated from source

系统 SHALL 能够仅根据版本控制中的 `nodes/` 定义和 `tools/nodes` 构建工具生成 `src/anyimage/assets/O_AnyImage.blend`。生成文件 SHALL 不纳入 Git 版本控制。

#### Scenario: Build from a clean checkout
- **WHEN** 干净源码检出中不存在 `O_AnyImage.blend` 并执行节点资产构建
- **THEN** 构建成功生成包含全部既定节点组的资产文件

#### Scenario: Rebuild an existing asset
- **WHEN** 输出路径已有本地生成的节点资产并再次执行构建
- **THEN** 文件被当前源码生成的完整资产替换，不产生 `.blend1` 备份

### Requirement: CI validates generated node assets

测试 CI SHALL 通过统一的 `node-group` 入口和固定版本的 `bpy` wheel，在运行节点资产相关测试前生成并独立校验节点资产，不得要求额外的 Blender 应用程序安装。

#### Scenario: Validate a pull request
- **WHEN** 测试工作流检出不含节点资产的源码
- **THEN** 工作流生成资产、校验保存结果并运行读取该资产的测试

#### Scenario: Reject an invalid generated asset
- **WHEN** 节点源码生成的资产未通过接口、结构或基本求值检查
- **THEN** CI 在运行后续发布步骤前失败

### Requirement: Release packages contain the generated asset

发布 CI SHALL 在测试和打包前生成并验证节点资产。每个平台扩展归档 MUST 包含 `assets/O_AnyImage.blend`，打包器 MUST 在资产缺失时明确失败。

#### Scenario: Package a release
- **WHEN** 发布工作流从干净源码构建扩展
- **THEN** 每个平台归档包含本次工作流生成并验证的节点资产

#### Scenario: Package without building assets
- **WHEN** 打包器运行时 `O_AnyImage.blend` 不存在
- **THEN** 打包立即失败并提示先构建节点资产
