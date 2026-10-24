# edition-packaging Specification

## Purpose
从共享本地功能实现和相同节点资产构建 Base 与 AI 扩展包，使版本清单对应实际依赖，并通过统一命令构建和验证最终发行产物。

## Requirements

### Requirement: Editions share one implementation of local features

打包器 SHALL 从同一份基础业务源码和各版明确入口组装独立安装包，通过显式 AI 排除清单及总入口替换确定 Base 内容。基础模块 SHALL 独立于 AI 模块导入和执行。

#### Scenario: Build Base from a clean checkout
- **WHEN** 从干净检出组装 Base
- **THEN** 归档包含完整基础实现与 Base 入口，安装运行无需另一版本提供模块

#### Scenario: Update shared behavior
- **WHEN** 修改基础业务实现并构建两版
- **THEN** 两版包含同一更新，基础业务源码、公共注册和界面交互只维护一份；完整版可直接从 `src/anyimage` 调试

### Requirement: Editions share identical node assets

每次打包 SHALL 构建一次节点资产，并将同一个完整 `O_AnyImage.blend` 装入两版各平台归档。节点组名称和加载协议 SHALL 保持现状。

#### Scenario: Compare release assets
- **WHEN** 检查同次构建的六个归档
- **THEN** 各归档的 `assets/O_AnyImage.blend` 字节完全一致

### Requirement: Edition manifests reflect actual dependencies

两版 SHALL 使用同一项目版本号及各自名称和 ID。Base SHALL 只声明并携带本地功能必需的 wheels，保留所需文件权限，移除 AI 网络权限。依赖版本 SHALL 维护单一来源并支持现有平台及 Python ABI。

#### Scenario: Validate Base manifest
- **WHEN** 读取 Base Manifest 及实际 wheels
- **THEN** ID 为 `anyimage_base`、名称为 `AnyImage Base`，版本与项目一致，依赖声明与归档内容一致且不包含 blendjob，权限说明符合基础功能

### Requirement: One command packages both editions

`uv run pack` SHALL 默认为 `windows-x64`、`macos-arm64`、`linux-x64` 各构建两版。`--platform` SHALL 限制目标平台，`--edition full|base` SHALL 允许单版构建。`--local` SHALL 保持完整版本地同步语义，拒绝 Base 本地同步组合并说明原因。

#### Scenario: Build all archives
- **WHEN** 运行 `uv run pack`
- **THEN** 生成六个归档，名称分别遵循 `AnyImage.v<version>.<platform>.zip` 与 `AnyImage_Base.v<version>.<platform>.zip`

#### Scenario: Build one platform
- **WHEN** 运行 `uv run pack --platform windows-x64`
- **THEN** 生成该平台的两个版本

#### Scenario: Build Base only
- **WHEN** 运行 `uv run pack --edition base --platform windows-x64`
- **THEN** 只生成该平台的 Base 归档

### Requirement: Release validates actual edition artifacts

同一次版本标签触发的 Release CI SHALL 校验两版身份、版本、文件内容、依赖与共同节点资产，执行相关行为测试及 Blender 官方扩展校验，并在成功后将六个 ZIP 上传同一草稿 Release。Base SHALL 在不含完整版及 AI 依赖的运行环境中验证。

#### Scenario: Publish draft artifacts
- **WHEN** 六个归档及相关验证全部通过
- **THEN** 同一个草稿 Release 包含两版三个平台的归档，含空格的 Base 文件名得到正确处理

#### Scenario: Reject contaminated Base
- **WHEN** Base 出现 AI 专用文件、依赖或悬空导入
- **THEN** 验证失败，流水线不进入发布步骤

#### Scenario: Validate offline and read-only installation
- **WHEN** 在关闭联网且安装目录只读的 Blender 中使用 Base
- **THEN** 基础功能正常，临时文件和用户数据写入允许的用户目录
