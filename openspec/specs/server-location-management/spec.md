# server-location-management Specification

## Purpose
管理服务器安装位置的选择、已有安装的发现和偏好设置入口，处理迁移目标冲突，确保完整迁移后的环境仍可使用且数据安全。

## Requirements

### Requirement: Installation location selection

系统 SHALL 在 AI 安装提示中提供以 Server Location 标注的存放目录选择及实际根目录预览。安装与迁移 SHALL 统一使用所选目录中的 `.anyimage`，自动检查其中是否存在安装。误选末级名为 `.anyimage` 的目录时 SHALL 提示选择父目录并阻止确认。既有配置 SHALL 按实际根目录保留。

#### Scenario: Select another drive
- **WHEN** 用户选择 `D:\` 并确认安装
- **THEN** 环境、模型、Job 文件与日志使用 `D:\.anyimage`

#### Scenario: Select a custom containing folder
- **WHEN** 用户选择 `D:\AI`
- **THEN** 实际根目录为 `D:\AI\.anyimage`，探测该目录的安装状态

#### Scenario: Select the installation folder by mistake
- **WHEN** 用户选择 `D:\.anyimage`
- **THEN** 提示选择其父目录 `D:\`，阻止确认并保持原配置

#### Scenario: Cancel selection
- **WHEN** 用户取消位置选择或确认
- **THEN** 原配置和原数据保持不变

### Requirement: Existing installation detection

系统 SHALL 按目标目录验证安装的平台、环境契约和实际启动能力，复用有效安装及模型，并明确展示需要补全的下载。无法识别的非空目标 SHALL 报告冲突。

#### Scenario: Use a complete installation offline
- **WHEN** 目标存在有效环境和默认模型，用户确认使用且网络访问关闭
- **THEN** 系统保存目标位置并刷新状态，无需下载

#### Scenario: Complete a partial installation
- **WHEN** 目标为可识别安装但缺少环境或默认模型
- **THEN** 提示缺失内容，经确认后补全，保留有效模型

#### Scenario: Unrelated target data
- **WHEN** 实际目标目录非空且无法识别为 AnyImage 安装
- **THEN** 系统报告冲突并保留目标数据与当前配置

### Requirement: Preferences location controls

Preferences SHALL 展示只读实际根目录；环境未安装时显示安装入口，已安装时显示迁移入口。安装、下载、推理和维护期间 SHALL 禁用位置变更。

#### Scenario: Installed environment
- **WHEN** 当前环境已安装
- **THEN** Preferences 显示实际路径、安装状态和 Move AI Server 按钮

#### Scenario: Select a migration destination
- **WHEN** 用户在迁移的文件夹选择器中选定存放目录
- **THEN** 系统直接启动迁移任务

#### Scenario: Missing environment
- **WHEN** 当前环境未安装
- **THEN** Preferences 显示 Set Up AI Server 入口并可在安装提示中选择位置

### Requirement: Safe complete migration

系统 SHALL 在独占维护状态停止 Server 后迁移整个根目录，验证文件及新环境可运行后才保存新配置并删除旧根目录。迁移 SHALL 提供进度和失败信息、处理重启恢复，并在源目录删除后才报告成功。

#### Scenario: Cross-drive success
- **WHEN** 用户确认从 C 盘迁移到 D 盘空目标
- **THEN** 系统复制并验证完整数据及环境，保存新位置并删除源目录，确认 Server 在源目录删除后仍可运行，再报告成功

#### Scenario: Failure before switching
- **WHEN** 空间不足、文件占用、复制失败、环境验证失败或用户在切换前取消
- **THEN** 原配置与源数据保留，清理本次临时副本并报告原因

#### Scenario: Unwritable destination
- **WHEN** 用户选择的安装目录无法创建目录或写入文件
- **THEN** 系统中止迁移，保留源安装与当前配置，提示选择有写入权限的文件夹

#### Scenario: Server controls during migration
- **WHEN** 后台正在迁移 Server
- **THEN** 启动、停止、重启、打开日志及卸载模型入口禁用，取消入口仅在配置切换前可用

#### Scenario: Source cleanup failure
- **WHEN** 已保存新位置但源目录清理失败
- **THEN** 使用新安装并提示残留路径，保持迁移待清理状态，支持重试且清理完成前不报告迁移成功

#### Scenario: Restart during migration
- **WHEN** Blender 在复制期间或切换后清理前退出并重启
- **THEN** 根据迁移阶段恢复明确状态，不删除仍在使用的安装

### Requirement: Migration target conflicts

系统 SHALL 拒绝源目标嵌套关系，识别同一目录，并在目标非空时阻止迁移覆盖。

#### Scenario: Target already installed
- **WHEN** 迁移选择的实际目标已有有效安装
- **THEN** 报告目标冲突，保留当前配置和两处数据，要求另选空目标

#### Scenario: Same or nested location
- **WHEN** 实际目标与源相同或互为祖先目录
- **THEN** 相同路径不搬迁，嵌套路径报告错误

### Requirement: Usable relocated environment

系统 SHALL 按需调整 Python 环境，验证迁移后 Server 不依赖原根目录，能够启动、加载模型和执行任务。根目录内的缓存 SHALL 随整体迁移。

#### Scenario: Run after migration
- **WHEN** 已迁移到 D 盘并删除原根目录
- **THEN** 新位置的环境能够启动 Server、加载模型和执行任务
