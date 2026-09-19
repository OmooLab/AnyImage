## Why

几何主线、计算支线和长连接分阶段调整时，容易造成横向拉长、支线归属不清及连线密集。将已选定的“结构与通道联合规划”方案统一用于全部几何节点资产，保持横向计算层次、清楚的分块和自然起伏的主线。

## What Changes

- 根据最近的几何消费者识别相连的计算支线，按支线局部读取接口值。
- 将计算块与共享连接通道共同纳入空间规划，再创建节点位置、Reroute 和 Frame。
- 保留选定版本的横向层次与共享长连接通道，以实际可追溯性评估画面。
- 用通用排列器替换原有逐层补救流程，应用于全部 7 个几何节点组。
- 验证排列前后运算、接口、连接及几何结果一致，并更新保存资产。

## Capabilities

### New Capabilities

- `joint-geometry-node-layout`: 联合规划几何节点的计算块与连接通道，并统一构建、验证资产布局。

### Modified Capabilities

## Impact

涉及 `tools/nodes/arrangement/`、`tests/tools/nodes/test_arrangement.py` 和 `src/anyimage/assets/O_AnyImage.blend`。沿用现有构建与预览入口，无新增依赖或节点组公开接口变更。
