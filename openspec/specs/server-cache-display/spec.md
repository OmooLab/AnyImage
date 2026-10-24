# server-cache-display Specification

## Purpose
TBD - created by archiving change show-server-controls-while-running. Update Purpose after archive.
## Requirements

### Requirement: Cached model list layout
Server 面板 SHALL 显示所有 Cached 模型名称，并 SHALL 在存在多个模型时让每个模型名称占据独立的视觉行。

#### Scenario: Multiple models are cached
- **WHEN** Server 为 Running 且 Cached 列表包含两个或更多模型
- **THEN** 面板逐行显示每个模型名称，并保留缓存清理按钮

#### Scenario: One model is cached
- **WHEN** Server 为 Running 且 Cached 列表只包含一个模型
- **THEN** 面板在一行内显示 `Cached` 与该模型名称，并保留缓存清理按钮

#### Scenario: No model is cached
- **WHEN** Server 为 Running 且 Cached 列表为空
- **THEN** 面板显示 `Cached: None`，并保留缓存清理按钮

### Requirement: Model cache can be unloaded from image context menus

AnyImage SHALL 在共用图片操作菜单中提供现有 `Unload Models` 操作，使用户可以主动释放全部模型 Session而不删除模型文件。

#### Scenario: Image context menu while Server is ready
- **WHEN** AI Environment 已安装且 Server 状态为 `READY`
- **THEN** Image Empty、AnyImage object 和 Image Texture node 的 AnyImage 右键菜单显示可用的 `Unload Models`

#### Scenario: Context menu while Server is busy
- **WHEN** Server 状态为 `BUSY`
- **THEN** `Unload Models` 不可执行，当前 Job 与模型 Session 不被并发清理

#### Scenario: Context menu while Server is stopped
- **WHEN** Server 未运行
- **THEN** `Unload Models` 不可执行，选择该操作不会为了清理模型而启动 Server

#### Scenario: User unloads models
- **WHEN** 用户在 Server 为 `READY` 时执行 `Unload Models`
- **THEN** 系统清空全部缓存 Session、保留已下载模型文件并保持 Server 运行

### Requirement: Model status uses stable catalog identities
服务端加载状态 SHALL 以稳定模型 key 表示每个已加载模型，空槽 SHALL 使用明确空值。模型目录 SHALL 声明档位，Preferences、模型枚举和 Server Panel SHALL 从该目录读取显示名称与档位。

#### Scenario: A display name changes
- **WHEN** 模型 label 改变但模型 key 与档位声明保持不变
- **THEN** 加载身份和档位保持正确，界面使用更新后的显示名称

#### Scenario: Catalog entries are reordered
- **WHEN** 模型目录中的条目顺序调整
- **THEN** 各模型的 Fast/Base/Pro 档位保持其显式声明值

#### Scenario: Loaded state is displayed
- **WHEN** Server Panel 读取已加载与空模型槽
- **THEN** 当前任务行、加载指示与卸载入口保持原有布局，档位由非空模型 key 对应的目录记录提供
