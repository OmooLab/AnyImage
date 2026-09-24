## MODIFIED Requirements

### Requirement: Boundary-specific smoothing strength

`O Image Depth Cutout` SHALL 使用单个 `Boundary Smooth` 输入控制边界平滑次数。Split 边 SHALL 使用完整 `Smooth Weight`，原始 Outline SHALL 使用 `0.1` 倍 `Smooth Weight`；两类影响相交时 Split 强度 MUST 优先。正厚度的同源 Front 与 pre-flipped Rear leaf SHALL 共同进入唯一一次 Boundary Smooth Repeat，并分别获得与相同 raw leaf 独立执行时等价的边界位移。

最终 smoothing weight SHALL 在 Front / Rear 分支前的单层最终 projection topology 上完成计算并保存。共同 Repeat SHALL 直接消费该最终权重，不得在 Join 后使用 raw cut marker 重新计算 influence。

#### Scenario: Separate Split and Outline response

- **WHEN** 同一网格同时存在 Split 边与原始 Outline 且启用 Boundary Smooth
- **THEN** Split 边按完整 Smooth Weight 平滑
- **AND** 仅受 Outline 影响的点按其 0.1 倍平滑

#### Scenario: Split and Outline intersection

- **WHEN** Split 与 Outline 的两圈影响范围相交
- **THEN** 相交区域使用两者中较强的 Split influence

#### Scenario: Front 与 Rear 不因共同执行减弱

- **WHEN** 正厚度 Front 与 Rear 作为断开 mesh island 共同执行 Boundary Smooth
- **THEN** 每张 leaf 的边界目标、Pin Sharp 权重和最终位移 SHALL 与其独立执行参考处于浮点容差内
- **AND** 边界条带采样不得跨越到另一张 leaf

#### Scenario: Front 与 Rear 使用相同生成阶段

- **WHEN** Boundary Smooth 从投影阶段移动到 leaf 构造后的阶段
- **THEN** Front 与 Rear SHALL 都由同一份未平滑投影拓扑生成后再平滑
- **AND** 不得先平滑 Front 再以它生成 Rear

#### Scenario: Cut marker 不进入叶片平滑

- **WHEN** projection topology 已完成 CONNECTED merge
- **THEN** 系统 SHALL 在该单层几何上计算 Outline、Split 与 Depth Limit 的最终 smoothing weight
- **AND** raw cut marker SHALL 保留到共同 Repeat 消费最终权重之后，再由输出清理
- **AND** 两张 leaf SHALL 继承相同的 Point-domain 最终权重
