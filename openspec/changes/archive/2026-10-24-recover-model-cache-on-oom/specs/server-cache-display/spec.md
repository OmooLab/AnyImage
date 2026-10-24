## ADDED Requirements

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
