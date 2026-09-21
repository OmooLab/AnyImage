## ADDED Requirements

### Requirement: Depth Cutout exposes an object-space far cull distance
`O Image Depth Cutout` SHALL 在主输入区公开 `Depth Limit`，使用最小值为 `-1` 的 `DISTANCE` 输入。该值 SHALL 表示从参考平面沿对象局部 +Y 方向保留几何的最大距离，负值 SHALL 允许裁切进入参考平面之前。

#### Scenario: Set a one-meter limit
- **WHEN** `Depth Limit` 为 `1 m`
- **THEN** 投影后局部 Y 大于 `1 m` 的几何 SHALL 被删除
- **AND** 局部 Y 不大于 `1 m` 的点 SHALL 保留

### Requirement: Far culling uses the projected position
Depth Cutout SHALL 使用与 Depth Split 相同的面中心相机深度采样，并应用 `Uniform Scale`、`Reference Depth` 与 `Depth Scale` 的投影公式得到面中心对象空间 Y。系统 MUST NOT 把 `Depth Limit` 当作相机原始深度值比较，也 MUST NOT 改用点域深度采样。

#### Scenario: Change reference depth
- **WHEN** 用户修改 `Reference Depth`
- **THEN** 几何的对象空间 Y 位置 SHALL 按既有投影公式更新
- **AND** 远端裁切 SHALL 根据更新后的位置重新求值

#### Scenario: Change depth scale
- **WHEN** 用户修改 `Depth Scale`
- **THEN** 几何的对象空间 Y 位置 SHALL 按既有投影公式缩放
- **AND** `Depth Limit` SHALL 保持同一个对象空间距离阈值

### Requirement: Far culling shares the Depth Split boundary pipeline
Depth Cutout SHALL 删除面中心对象空间 Y 大于 `Depth Limit` 的面，并把保留面与删除面的交界边写入 Depth Split 使用的切边标记。Depth Limit 边 SHALL 与 Depth Split 边共同经过 Balloon profile 衰减、边界平滑、法线与 Balloon / Shell 厚度闭合流程。

#### Scenario: Cull a thick Depth Cutout
- **WHEN** 投影面包含面中心越过 `Depth Limit` 的面且 Thickness 大于零
- **THEN** 越界面 SHALL 在厚度生成前删除
- **AND** 新裁切边的厚度修正值与闭合行为 SHALL 等同于 Depth Split 切边
- **AND** 输出 MUST NOT 包含破面或由越界面生成的前面、侧壁或背面

### Requirement: New Depth Cutouts receive a median-based limit
系统 SHALL 在当前 Cutout 选区及深度纹理有效域内计算中位深度，并在创建 Depth Solid 或 Depth Symmetry 时将 `1.2 × median_depth` 对应的对象空间距离写入 `Depth Limit`。换算 SHALL 使用 `max((1.2 × median_depth − reference_model_depth) × uniform_scale, 0)`，其中创建时 `Depth Scale` 为 1。

#### Scenario: Create from usable selected depth
- **WHEN** 当前选区包含有效深度样本
- **THEN** `Depth Limit` SHALL 对应相机深度中位数的 1.2 倍
- **AND** 该值 SHALL 使用与 `Reference Depth` 相同的选区和深度有效性规则

#### Scenario: Create without usable selected depth
- **WHEN** 当前选区没有有效深度样本
- **THEN** 中位深度与参考深度 SHALL 使用既有 reference baseline 回退
- **AND** Depth Cutout SHALL 仍成功创建并获得非负 `Depth Limit`

### Requirement: Node assets contain the far cull control
构建后的 `O_AnyImage.blend` SHALL 在 `O Image Depth Cutout` 中保存 `Depth Limit` 接口及投影后裁切连线。

#### Scenario: Build and verify node assets
- **WHEN** 执行节点资产构建与验证
- **THEN** 保存的 `O Image Depth Cutout` SHALL 包含 `Depth Limit`
- **AND** 资产检查 SHALL 确认 Depth Limit 使用面采样并接入 Depth Split 边界处理链
