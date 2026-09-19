## ADDED Requirements

### Requirement: Geometry graphs prohibit Capture Attribute

全部生产几何节点定义、嵌套几何组、保存资产及相关测试辅助图 MUST 不使用 GeometryNodeCaptureAttribute。

#### Scenario: Inspect definitions and saved assets
- **WHEN** 分别构建节点定义并加载保存资产，递归检查全部几何组及嵌套组
- **THEN** 每个已访问几何组的 Capture Attribute 数量均为零

### Requirement: Fields are consumed directly when evaluation is equivalent

字段 SHALL 在消费位置直接连接，明确必要域转换；跨几何变化时 SHALL 优先审查调整消费顺序及源几何采样，以减少中间存储。多个消费者或跨区域连线 MUST 不作为存值的充分理由。

#### Scenario: Reuse a field without geometry changes
- **WHEN** 多个消费者所在几何状态、域、类型与输入属性版本允许等价求值
- **THEN** 消费者直接使用字段及必要域转换，保持原结果而不新增存储

#### Scenario: Consume a field after topology changes
- **WHEN** 切分、删面、挤出或合并改变源字段求值上下文
- **THEN** 实现明确源几何与映射，验证结果等价，并仅保存无法通过合理调整消费或采样消除的必要数据

### Requirement: Named storage has an explicit purpose and lifetime

每处 Store Named Attribute SHALL 有明确的实际消费者与存储必要性，记录名称、类型、域、Selection 和阶段。必要命名协议 SHALL 保留；临时属性 SHALL 在最后消费者后清理，并保留已有用户属性。

#### Scenario: Preserve material protocols
- **WHEN** 输出几何供材质消费 UVMap 或 o_normal_scale
- **THEN** 属性域与数值保持正确，包括角 UV 以及正背面和侧壁掩码

#### Scenario: Finish consuming temporary data
- **WHEN** 几何处理完成临时命名数据的最后一次消费
- **THEN** 最终输出不携带新增内部临时属性，且输入已有用户属性的名称、类型和值按原行为保留

### Requirement: Geometry behavior and graph readability are preserved

重构 SHALL 保持修改器接口、几何结果、UV 和材质行为，并逐组检查字段消费关系与完整节点布局的可读性。

#### Scenario: Validate depth processing
- **WHEN** 使用非均匀深度测试 Split 开关、零与正厚度、独立重叠表面、Balloon/Uniform、圆化、膨胀及法线平滑
- **THEN** 实际几何与实施前行为基线等价，索引重排按拓扑和对应几何数据比较

#### Scenario: Validate cut boundary smoothing and panorama
- **WHEN** 对原轮廓、切分边界、平滑迭代和 Panorama 接缝、极点、无效像素及 Valid Only 求值
- **THEN** 原轮廓保护、影响范围、固定映射、球面采样与 UV 保持预期行为

#### Scenario: Inspect material inheritance
- **WHEN** 输入为空或带有多个材质槽，执行 Image Plane 或 Panorama 的材质继承
- **THEN** 材质槽及面材质索引符合原行为，生成几何保留且输入来源几何正确处理

### Requirement: Rules tests and saved assets agree

项目规范及当前节点资产说明 SHALL 明确禁止 Capture 并采用一致的字段传递规则。测试 SHALL 覆盖结构约束与真实行为；节点资产 SHALL 重建并经过独立加载验证，相关测试及全量测试正常退出后完成交付。

#### Scenario: Deliver a geometry graph change
- **WHEN** 本次节点整理完成
- **THEN** 源码、规范、测试和 O_AnyImage.blend 同步，Capture 旧结构断言已替换，uv run node-group build 与 uv run pytest 成功且正常退出
