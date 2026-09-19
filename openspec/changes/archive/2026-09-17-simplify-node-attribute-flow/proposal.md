## Why

几何节点中存在仅为传递中间字段而写入、读取命名属性的链路，增加节点数量和隐式依赖。现行节点资产规范以跨区域连线作为命名存储的依据，需要统一改为按字段求值上下文与数据生命周期选择传递方式。

## What Changes

- 全面检查构建入口中的几何节点组及共享构建函数，沿几何链、字段链和外部消费者记录命名属性的存取域、求值时机与用途。
- 同一几何状态与等价求值域中的中间字段优先直连；显式保留必要的域转换，删除冗余存取及失去用途的清理节点和辅助函数。
- 需要固定变形前、拓扑变化前或分支源几何上的值时优先使用 Capture Attribute；需要按名称供材质、输入网格或其他消费者访问的属性继续使用命名属性。
- 调整受节点数量变化影响的构建接线，使用明确返回的节点或 socket 引用表达业务连接。
- 更新 `AGENTS.md` 与 `docs/internals/node-assets.md` 的节点属性规范，按新规范统一整理节点连线。
- 更新相关测试，重建并验证 `.blend` 资产，确认几何、UV、材质与修改器接口行为一致。

## Capabilities

### New Capabilities

无。本变更属于内部节点重构与开发规范调整，使用 `skip_specs: true`。

### Modified Capabilities

无。保持现有公开接口和几何行为。

## Impact

- `tools/nodes/common`、`tools/nodes/groups`，重点是 Depth Surface、Depth Cutout 和 Panorama。
- `tools/nodes/arrangement` 的现有布局能力与相关测试需验证能正确处理直连及匿名属性；仅在发现实际问题时修改。
- `tests/tools/nodes`、相关 Operator 与材质测试、`src/anyimage/assets/O_AnyImage.blend`。
- `AGENTS.md`、`docs/internals/node-assets.md`。
