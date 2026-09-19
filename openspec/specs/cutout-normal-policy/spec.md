# cutout-normal-policy Specification

## Purpose
TBD - created by archiving change reorganize-cutout-shapes. Update Purpose after archive.
## Requirements
### Requirement: Normal Map 勾选仅控制本地形态
Normal Map 勾选 SHALL 仅控制 Flat 和 Solid 的法线生成；两个 Depth 入口 SHALL 始终生成并使用法线图，且不改写用户保存的勾选值。工具说明 SHALL 明确该作用范围。

#### Scenario: Flat 与 Solid 关闭法线
- **WHEN** AI 可用且勾选关闭，用户创建 Flat 或 Solid
- **THEN** 系统使用 NONE 法线模式

#### Scenario: Flat 与 Solid 开启法线
- **WHEN** AI 可用且勾选开启，用户创建 Flat 或 Solid
- **THEN** 系统请求 TANGENT 法线并连接结果材质

#### Scenario: Depth Solid 自动法线
- **WHEN** 用户创建 Depth Solid，无论勾选保存为真或假
- **THEN** 系统请求 OBJECT 法线并正确加载、按输出轴向处理和连接材质

#### Scenario: Depth Balloon 自动法线
- **WHEN** 用户创建 Depth Balloon，无论勾选保存为真或假
- **THEN** 系统请求 TANGENT 法线并连接结果材质

### Requirement: 所有调用路径采用一致策略
法线策略 SHALL 在 Operator 业务层统一解析，Job 参数与结果接收使用同一策略。

#### Scenario: 绕过 Pie 调用
- **WHEN** 直接调用 Operator 创建任一 Depth 形态并传入 generate_normal 为 false
- **THEN** 法线仍按该深度入口生成和应用，与 Pie 调用结果一致

### Requirement: AI 可用性继续限制入口
AI 未就绪时系统 SHALL 仅提供 Flat 与 Solid，忽略遗留的开启法线选项；AI 就绪时 SHALL 提供四个入口。

#### Scenario: 未就绪的本地创建
- **WHEN** AI 未就绪、保存的 Normal Map 为真，用户创建 Flat 或 Solid
- **THEN** 创建过程不因该遗留值启动 AI Job，法线模式为 NONE

### Requirement: 法线适配跟随当前几何
Flat 与 Solid 共用节点组后的法线适配 SHALL 支持厚度变化，Depth 入口 SHALL 保持各自法线空间和轴向转换正确。

#### Scenario: Flat 增厚
- **WHEN** 带法线的 Flat 调整为 Balloon 正厚度
- **THEN** 材质按当前几何参与法线适配，不因初始 Flat 预设而缺失 Balloon 所需连接

#### Scenario: 深度入口轴向与双面
- **WHEN** 分别检查两个 Depth 入口的 -Z、+X 输出，以及 Depth Balloon 的 Double Sided 开关
- **THEN** 对应法线图被正确加载和连接，前后表面的着色方向与几何一致

