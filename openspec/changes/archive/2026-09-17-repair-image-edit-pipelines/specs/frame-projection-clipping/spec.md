## Purpose

定义 Frame 在透视观察平面附近的连续交叠判定，确保可见且可稳定求交的图片区域能够参与取景，并固定结果透明颜色和无效交叠时的对象保留行为。

## ADDED Requirements

### Requirement: Frame accepts a finite visible intersection
Frame SHALL 依据画框内的连续有效投射判断正面积交叠。完整源图片的角点接近无穷远 SHALL NOT 导致画框内稳定有效的交叠被拒绝。

#### Scenario: Tilted source crosses the perspective origin
- **WHEN** 30° 倾斜源平面位于视图深度 0.2 且部分跨越观察平面，透视 X/Y 焦距系数为 1.7、2 或 4，Frame 内有正面积前方交叠
- **THEN** Frame 接受交叠并生成结果
- **AND** 对应有效源坐标与实际采样保持一致

#### Scenario: Source lies extremely close in front
- **WHEN** 源平面非常接近观察原点但画框内仍存在数值可稳定表达的正面积前方交叠
- **THEN** Frame 接受交叠，不因源角点的远距离屏幕投射取消操作

#### Scenario: Orthographic source has non-positive depth
- **WHEN** 正交 Frame 与具有有限非正视图深度的源平面存在稳定正面积交叠
- **THEN** Frame 正常完成

### Requirement: Invalid active overlap preserves inputs
Frame SHALL 在 active 图片与画框没有稳定正面积交叠时以 warning 取消，并保留全部参与对象的图片、变换和存在状态。

#### Scenario: Frame only touches an edge or misses the source
- **WHEN** Frame 仅接触 active 图片投射边缘，或没有有效交叠
- **THEN** 操作取消，源对象与源图片均保持不变

### Requirement: Frame preserves independent color and alpha output
Frame SHALL 保留底层原色与前景混合得到的 RGB、独立累积的 Alpha 及边界子像素覆盖。源内透明 RGB SHALL 保留，完全未覆盖 Canvas SHALL 为 RGBA 全零。

#### Scenario: Frame result is revealed by Mask Add
- **WHEN** 多层 Frame 含透明底色与半透明前景，随后执行 Mask Add
- **THEN** 恢复区域显示原合成 RGB，源外透明 Canvas 的 RGB 保持为零
- **AND** 分块高度变化不会改变合成结果
