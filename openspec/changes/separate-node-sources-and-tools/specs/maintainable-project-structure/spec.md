## MODIFIED Requirements

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
