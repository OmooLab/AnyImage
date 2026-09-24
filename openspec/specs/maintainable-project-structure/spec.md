# maintainable-project-structure Specification

## Purpose
TBD - created by archiving change remove-debug-workflows. Update Purpose after archive.
## Requirements
### Requirement: Tests protect meaningful behavior

维护者 MUST 审查全部测试文件、用例和辅助代码，按实际回归风险保留、合并、重写或删除。保留的测试 SHALL 验证可观察行为或关键协议，每项独有且仍适用的风险覆盖 MUST 保留。

#### Scenario: Audit completed
- **WHEN** 全部测试整理完成
- **THEN** 失效功能测试和无独立价值的重复测试已删除，保留用例能说明所保护的行为，完整测试通过

### Requirement: Test names reflect tested functionality

测试文件、类和函数 MUST 与其验证的功能、行为和关键条件相符；跨独立职责的测试集合 SHALL 按稳定功能拆分。

#### Scenario: Locate a behavior test
- **WHEN** 按测试路径、类名和函数名查找某项功能
- **THEN** 名称与测试主体的实际断言对应，共用辅助代码拥有明确的复用职责

### Requirement: Node asset modules reflect responsibilities

根目录 `nodes/` 的模块 MUST 只包含节点组及其共用构建定义，`tools/nodes/` MUST 只包含构建入口、布局、资产校验和预览工具。所有移动 MUST 同步导入、wheel 包清单、构建与验证入口及测试路径，并删除旧路径和转发层。

#### Scenario: Load reorganized node definitions
- **WHEN** 构建工具和节点行为测试导入节点组定义
- **THEN** 导入指向 `nodes.groups` 或 `nodes.common`，不存在 `tools.nodes.groups` 或 `tools.nodes.common` 兼容路径

#### Scenario: Load node asset tools
- **WHEN** 启动器加载节点构建、布局、验证或预览模块
- **THEN** 工具从 `tools.nodes` 加载，并从顶层 `nodes` 包使用节点定义

#### Scenario: Preserve node behavior
- **WHEN** 对重组后的节点构建函数运行针对性测试
- **THEN** 节点组名称、接口、默认值、运算、连接、布局和求值与重组前一致

#### Scenario: Locate node tests
- **WHEN** 维护者按测试路径查找节点相关覆盖
- **THEN** 节点定义行为测试位于 `tests/nodes`，构建与资产工具测试位于 `tests/tools/nodes`

### Requirement: Internal documentation matches implementation

`docs/internals/` 全部页面 MUST 与最终源码中的功能、职责、参数、调用链和产物对应，页面名称和目录索引 MUST 与主题对应。实现流程 SHALL 使用从上到下的 Mermaid 图。

#### Scenario: Read final implementation documentation
- **WHEN** 按总览或 MkDocs 导航访问任一内部主题
- **THEN** 链接有效，内容描述当前实现，源码路径和功能名称可核对，Debug 专页和过期 Debug 说明已清理

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

