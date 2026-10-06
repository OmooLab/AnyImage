## ADDED Requirements

### Requirement: Shared image and reference interfaces reflect ownership
公共图片创建与资源清理 SHALL 由职责明确的 common 接口提供。公共参考数据与 Scene 属性协调 SHALL 分层，跨模块调用 SHALL 使用明确的公共接口。移动模块 SHALL 同步真实调用者与测试引用，并删除旧路径及转发层。

#### Scenario: A Bake temporary color image is created
- **WHEN** Bake 准备需要拼接的临时 Color 图片
- **THEN** 系统复用公共图片创建和失败清理能力，保留源图片解释设置与精度

#### Scenario: Viewport uses polygon calculations
- **WHEN** Viewport 和测试调用已拆分的 Polygon 能力
- **THEN** 调用指向 Polygon 的公共接口和真实模块属主

#### Scenario: Scene reference properties are synchronized
- **WHEN** Scene 选择或图片编辑触发参考状态更新
- **THEN** Scene 协调层调用公共参考数据接口，公共参考数据模块不反向导入 Scene 属性协调层

### Requirement: Operator modules follow stable business responsibilities
去背景专属实现 SHALL 收拢到 `remove_background/` 包，由 `operators.py` 定义 Operator 入口、`__init__.py` 汇总导出和注册。颜色匹配 Operator 模块 SHALL 按 `color_match` 业务命名。所有类型迁移 SHALL 同步扩展注册及逆序注销清单。

#### Scenario: Locate HDR background behavior
- **WHEN** 维护者查找去背景的 HDR 输入、提交与 Undo 实现
- **THEN** 实现位于去背景业务包，多业务共用 HDR 能力仍通过 common 提供

#### Scenario: Locate color matching behavior
- **WHEN** 维护者查找匹配预览及结果提交
- **THEN** 入口位于颜色匹配模块，参考准备和管理拥有独立职责

### Requirement: Maintenance verification covers source and runtime behavior
整理 SHALL 保留实际行为覆盖，将共享测试辅助函数放入 `tests/support`，删除已查证无业务用途的实现和参数，并同步相关内部文档。真实 GPU 显示验证 SHALL 与 Mock 路径验证分别记录。

#### Scenario: Test responsibilities are organized
- **WHEN** 查找参考数据、Scene 属性及匹配 Operator 的行为测试
- **THEN** 各测试位于对应职责路径，共享辅助能力无需导入其他测试用例模块

#### Scenario: Preview encoding is verified
- **WHEN** 在实际 GPU 上检查共享预览 Shader
- **THEN** 中灰、图像方向及半透明边缘符合既有一次显示编码与 Alpha 约定，验证结果明确记录

#### Scenario: Node helpers are cleaned
- **WHEN** 删除无调用的节点构建帮助函数并完成资产构建验证
- **THEN** 节点接口和求值保持有效，生成资产 Capture Attribute 为零，旧函数引用清理

#### Scenario: Internal implementation references are read
- **WHEN** 访问整理后的 Common、架构、Operator 索引及产物协议
- **THEN** 文档路径、名称和职责对应最终源码，新增业务可以从索引定位
