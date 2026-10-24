## ADDED Requirements

### Requirement: Base provides local image workflows

AnyImage Base SHALL 独立提供剪贴板导入、普通平面、Frame、Mask、Rectify、Cutout Flat/Solid 与本地 Balloon、颜色参考与调色、Bake Mesh，与完整版对应本地功能行为一致。

#### Scenario: Use Base independently
- **WHEN** 用户在未安装完整版及 AI 环境的 Blender 中安装并启用 Base
- **THEN** 上述功能可使用，执行过程中无需 AI Server、模型或网络连接

### Requirement: Base excludes AI implementation

Base 安装包 MUST 排除 AI Server、AI Runtime、AI Operator、模型目录与下载配置、AI 专用辅助代码、设置、UI、翻译及 blendjob 等 AI 专用依赖。其功能入口 SHALL 不包含 AI 去背景、超分、深度/浮雕平面、Panorama、深度 Cutout 和 AI 法线生成。节点资产 SHALL 按双版打包契约完整共用。

#### Scenario: Inspect installed Base
- **WHEN** 解压 Base 归档并检查 Python、配置、翻译和 wheels
- **THEN** AI 专用内容不存在，全部基础模块的导入可由 Base 自身和 Blender 提供的依赖满足

#### Scenario: Inspect Base interface
- **WHEN** 打开 Base 偏好设置、菜单、面板和工具选项
- **THEN** 只显示基础功能，AI 功能及 Server 管理入口不存在

### Requirement: Editions have distinct extension identities

Base SHALL 使用显示名称 `AnyImage Base` 和 Manifest ID `anyimage_base`；完整版 SHALL 保持 `AnyImage` 和 `anyimage`。两版 SHALL 沿用相同内部 Blender 注册 ID、Scene 属性协议和快捷键，AddonPreferences SHALL 绑定各自实际包路径。

#### Scenario: Install both editions
- **WHEN** 用户安装两个版本但只启用一个
- **THEN** 扩展管理中可区分两版，当前版本的偏好设置绑定自身包，操作使用现有 anyimage 命名空间和快捷键

### Requirement: First enabled edition remains active

两版 SHALL 在任何注册或 Runtime 启动副作用前检查同一 Blender 进程内另一版的实际注册状态。发现冲突时 MUST 阻止后启用版本完成启用，提示先禁用当前版本，并保持先启用版本完整工作。仅安装另一版 SHALL 不阻止启用。

#### Scenario: Enable Base after full
- **WHEN** 完整版已启用，用户尝试启用 Base
- **THEN** Base 报告冲突，完整版的类型、菜单、属性、快捷键及 Runtime 保持原状

#### Scenario: Enable full after Base
- **WHEN** Base 已启用，用户尝试启用完整版
- **THEN** 完整版报告冲突，AI Runtime 不启动，Base 的注册状态与功能保持原状

#### Scenario: Switch editions
- **WHEN** 用户禁用当前版本后启用另一版
- **THEN** 另一版正常启用，场景属性协议和快捷键保持一致

#### Scenario: Cleanup rejected activation
- **WHEN** Blender 清理启用被拒绝的版本
- **THEN** 清理不删除先启用版本的任何注册内容

#### Scenario: Install in different repositories
- **WHEN** 两版位于不同扩展仓库且其中一版已启用
- **THEN** 后启用版本仍识别冲突，不依赖固定仓库模块路径
