## ADDED Requirements

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

`tools/node_assets/` 的全部模块 MUST 按实际资产或业务职责审查命名与边界，所有重命名 MUST 同步导入、构建与验证入口及测试路径，并删除旧路径和转发层。

#### Scenario: Load reorganized asset tools
- **WHEN** 启动器解析脚本并加载节点构建与验证模块
- **THEN** 所有路径指向最终模块，文件名与构建对象、几何处理、布局或验证职责对应

#### Scenario: Preserve node behavior
- **WHEN** 对重组后的节点构建函数运行针对性测试
- **THEN** 普通图像平面统一使用 `O Image Plane` 名称，源码使用 `image_plane`；资产重命名前后接口、默认值、运算、连接及布局一致

### Requirement: Internal documentation matches implementation

`docs/internals/` 全部页面 MUST 与最终源码中的功能、职责、参数、调用链和产物对应，页面名称和目录索引 MUST 与主题对应。实现流程 SHALL 使用从上到下的 Mermaid 图。

#### Scenario: Read final implementation documentation
- **WHEN** 按总览或 MkDocs 导航访问任一内部主题
- **THEN** 链接有效，内容描述当前实现，源码路径和功能名称可核对，Debug 专页和过期 Debug 说明已清理
