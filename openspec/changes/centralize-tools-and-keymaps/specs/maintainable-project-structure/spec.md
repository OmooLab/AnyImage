## ADDED Requirements

### Requirement: WorkspaceTool declarations are centralized
系统 MUST 在 `src/anyimage/tools.py` 中定义并统一注册全部 WorkspaceTool。`src/anyimage/operators/` SHALL 保留现有 Operator 和业务实现路径，但 MUST NOT 定义或导出 WorkspaceTool。扩展顶层入口 MUST 通过 `tools.py` 的单一生命周期注册和注销工具。

#### Scenario: Locate tool declarations
- **WHEN** 维护者查找 AnyImage 的 WorkspaceTool 定义和注册顺序
- **THEN** Frame、Mask、Rectify、Cutout 及其有序注册信息均位于 `src/anyimage/tools.py`

#### Scenario: Locate operator behavior
- **WHEN** 维护者查找任一工具关联的执行行为
- **THEN** 对应 Operator 和业务辅助代码仍位于原有 `src/anyimage/operators/` 路径，且不依赖 `tools.py`

### Requirement: Extension keymaps use one direct lifecycle
系统 MUST 在 `src/anyimage/keymaps.py` 中以常量声明全部扩展级 keymap 的功能、按键、事件和所属 Blender 面板，并统一创建、记录和清理 keymap item。注册流程 MUST 只遍历该常量，不包含具体功能绑定或功能专属可用性判断。具体 Operator 模块和扩展顶层入口 MUST NOT 各自实现 keymap item 生命周期，且 MUST NOT 为旧注册函数保留兼容入口。

#### Scenario: Register existing shortcuts
- **WHEN** 扩展完成注册
- **THEN** 3D View 与 Node Editor 的现有复制跟踪和图片粘贴快捷键由 `keymaps.py` 创建，并保持当前平台修饰键与事件不变

#### Scenario: Inspect shortcut definitions
- **WHEN** 维护者阅读 `keymaps.py` 中的常量
- **THEN** 无需阅读注册控制流程即可确定每项快捷键调用的 Operator、按键、事件、修饰键和所属 Blender keymap

#### Scenario: Unregister extension shortcuts
- **WHEN** 扩展被注销
- **THEN** `keymaps.py` 只移除自身创建的全部 keymap item，并清空内部注册记录

#### Scenario: Inspect current shortcut scope
- **WHEN** 检查本次变更注册的 keymap item
- **THEN** 不存在 Cutout 激活快捷键或其他新增用户快捷键
