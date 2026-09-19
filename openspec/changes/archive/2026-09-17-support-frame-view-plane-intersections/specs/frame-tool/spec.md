## ADDED Requirements

### Requirement: Frame samples every valid view-plane intersection
Frame SHALL 根据当前投影模式，以 Frame 屏幕位置对应的观察射线与每个参与 Image Empty 平面求交，并 SHALL 以有限且位于图片显示边界内的交点计算源像素坐标和几何深度。系统 SHALL NOT 仅因 Image Empty 的一个或多个角位于观察平面另一侧而取消整个操作。

#### Scenario: User finishes a frame in orthographic view at a non-positive view depth
- **WHEN** active Image Empty 在正交视图中具有有限稳定的屏幕投射，但其视图深度不为正
- **AND** Frame 与 active 图片的有效投射存在正面积交叠
- **THEN** 系统完成 Frame
- **AND** 结果保持操作时的正交屏幕图案

#### Scenario: Orthographic rays are parallel to the image plane
- **WHEN** 正交观察射线与 active Image Empty 平面平行，无法形成稳定的有限交点
- **THEN** 系统取消 Frame
- **AND** 所有参与对象保持不变

#### Scenario: A perspective image partially crosses the view plane
- **WHEN** Image Empty 的一部分位于透视观察方向前方，另一部分越过观察原点
- **AND** Frame 与 active 图片的有效前方投射存在正面积交叠
- **THEN** 系统采样 Frame 内观察方向前方的稳定平面交点
- **AND** 位于观察方向后方、与射线平行或超出图片边界的源样本为透明
- **AND** 系统不因完整图片无法形成有限凸四边形而取消操作

#### Scenario: A perspective image is extremely close but remains in front
- **WHEN** Image Empty 的有效交点位于透视观察方向前方且非常接近观察原点
- **AND** 屏幕到图片平面的映射仍可稳定求解
- **THEN** 系统允许该投射参与 Frame
- **AND** 系统不使用固定世界距离阈值拒绝整张图片

#### Scenario: A frame contains a ray parallel to one source plane
- **WHEN** Frame 中部分屏幕位置的观察射线与某个参与 Image Empty 平面平行
- **THEN** 该源在对应位置贡献透明样本
- **AND** 其他稳定位置及其他参与源继续正常采样与合成

### Requirement: Frame validates active overlap from the valid projection region
Frame SHALL 使用 active Image Empty 在当前投影模式下可稳定求交的连续几何区域判断 Frame 交叠。交叠 SHALL 具有正面积，且 SHALL 独立于 active 图片的 Alpha 和离散输出像素是否恰好命中该区域。

#### Scenario: The complete active projection is unbounded but its valid part overlaps the frame
- **WHEN** active Image Empty 跨越透视观察原点，其完整角点投影无法表示为有限凸 Quad
- **AND** 其观察方向前方的有效投射与 Frame 存在正面积交叠
- **THEN** 系统接受该 active 交叠并继续 Frame

#### Scenario: Only invalid or rear-facing intersections overlap the frame
- **WHEN** Frame 内不存在 active Image Empty 的稳定前方透视交点，或不存在稳定的正交交点
- **THEN** 系统以 warning 提醒用户 Frame 没有与 active Image Empty 的有效投射交叠
- **AND** 系统取消操作并保持所有参与对象不变

#### Scenario: A narrow valid overlap falls between output pixel centers
- **WHEN** Frame 与 active 有正面积有效几何交叠，但当前输出尺寸的像素中心没有命中该区域
- **THEN** 系统仍将该 Frame 视为具有 active 交叠
- **AND** 离散输出像素可以按实际采样结果保持透明

### Requirement: Perspective Frame uses a visible result depth
Frame SHALL 在透视视图中优先使用 active Image Empty 世界原点的正视图深度放置 view-facing 结果。当 active 原点不在观察方向前方、但 active 图片存在有效前方交叠时，系统 SHALL 使用 active 有效交叠区域屏幕几何中心对应的稳定正交点深度放置结果。系统 SHALL NOT 以任意常量深度替代无法求解的结果位置。

#### Scenario: Active origin remains in front of the perspective view
- **WHEN** active Image Empty 世界原点位于透视观察方向前方
- **THEN** 结果平面继续使用 active 原点的视图深度

#### Scenario: Active origin is behind while part of the image remains visible
- **WHEN** active Image Empty 世界原点不在透视观察方向前方
- **AND** active 图片的有效前方投射与 Frame 存在正面积交叠
- **THEN** 系统使用有效交叠区域屏幕几何中心与 active 图片平面的交点深度
- **AND** 结果 Image Empty 位于观察方向前方并覆盖用户所画 Frame

#### Scenario: No stable representative depth exists
- **WHEN** active 原点不能提供正深度，且有效交叠区域的代表射线无法稳定取得正交点深度
- **THEN** 系统取消 Frame
- **AND** 所有参与对象保持不变

