## Why

之前的属性整理将大量 Store Named Attribute 替换为 Capture Attribute，保留了中间值存储并增加跨阶段连线，偏离了直接消费字段、提高结构可读性的要求。当前七个几何节点组共有 21 个 Capture；规范与部分测试还在强制沿用这一方向，需要一并纠正。

## What Changes

- 全面检查全部几何节点、嵌套组与共享构建函数，禁止使用 Capture Attribute。
- 优先让字段在消费位置直接求值，显式表达必要域转换；通过调整处理顺序或源几何采样减少中间存储。
- 逐项论证 Store Named Attribute 的必要性：保留实际命名协议，以及确实需要跨几何变化保存的最少数据；禁止机械替换 Capture。
- 更新 AGENTS.md、节点资产规范和相关当前实现说明，统一禁止 Capture、优先直连的规则。
- 更新测试，移除依赖 Capture 的结构断言及测试辅助用法，检查全部资产与嵌套几何组中 Capture 为零，并验证真实几何行为。
- 重建节点资产，核对布局、接口、UV、材质与几何结果。

## Capabilities

### New Capabilities

- `geometry-field-flow`: 几何节点字段直连、必要命名存储、禁止 Capture 及对应资产验证规则。

### Modified Capabilities

无。

## Impact

- tools/nodes/common、tools/nodes/groups，以及实际受影响的排列代码。
- tests/tools/nodes、tests/support 及相关材质、Operator 测试。
- src/anyimage/assets/O_AnyImage.blend。
- AGENTS.md、docs/internals/node-assets.md 及检索确认受影响的当前内部说明。
- 公开接口、几何功能与属性协议保持一致；实施时保留工作区已有修改。该提案取代 simplify-node-attribute-flow 中关于 Capture 的设计决策。
