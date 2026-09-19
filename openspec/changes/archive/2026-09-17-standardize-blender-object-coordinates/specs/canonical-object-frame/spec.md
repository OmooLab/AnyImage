## ADDED Requirements

### Requirement: Generated meshes use the Blender object frame

系统 SHALL 让 Plane、Depth Plane、Relief Plane、Cutout BaseShape 与 Depth Cutout 的输入网格使用统一的 Blender 对象局部坐标：X 为图片水平方向，Z 为图片 up，+Y 为图片纸内深度方向。所有未应用 modifier 的输入网格 MUST 位于 `Y=0` 的 XZ 平面。

#### Scenario: Create a Plane or Cutout BaseShape

- **WHEN** 用户创建 Plane 或 Cutout BaseShape
- **THEN** 未应用 modifier 的本地顶点 Y 坐标均为 0
- **AND** 顶点 X 范围对应源 Image Empty 的水平 bounds
- **AND** 顶点 Z 范围对应源 Image Empty 的 up bounds

### Requirement: Image UV maps to the XZ plane

系统 SHALL 将源图片的左右方向映射到本地 X，将源图片的上下方向映射到本地 Z，并保持 UV 采样在生成网格上的方向一致。

#### Scenario: Cutout UV corners follow image corners

- **WHEN** Cutout 从完整图片 bounds 生成 BaseShape
- **THEN** 图片左下角对应的本地顶点位于最小 X 和最小 Z
- **AND** 图片右上角对应的本地顶点位于最大 X 和最大 Z
- **AND** UV 读取的颜色纹理方向与源图片一致

### Requirement: Depth and thickness operate along Y

系统 SHALL 让 Depth Plane、Relief Plane、Cutout 与 Depth Cutout 的投影、厚度和 Shell 位移沿本地 Y 方向表达，并 SHALL 让 front 方向为 -Y、depth/纸内方向为 +Y。

#### Scenario: Depth Plane displaces toward positive Y

- **WHEN** Depth Plane 使用有效深度图且 Reference Depth 大于采样深度
- **THEN** 生成表面的 Y 坐标向 +Y 方向偏离输入平面
- **AND** 输入平面保持在 `Y=0`

#### Scenario: Cutout thickness grows along Y

- **WHEN** Cutout 设置非零 Thickness
- **THEN** 生成 Shell 的前后范围沿 Y 轴分布
- **AND** 没有几何沿 Z 轴被当作厚度方向

### Requirement: Depth Direction defaults to positive Y

`O Image Relief Plane` 与 Depth Symmetry 的 canonical 深度方向 SHALL 使用本地 +Y 作为默认方向，而不是 -Z。

#### Scenario: Relief Plane direction default

- **WHEN** 用户从资产加载 `O Image Relief Plane`
- **THEN** `Depth Direction` 默认值为 `(0, 1, 0)`

#### Scenario: Depth Symmetry canonical direction

- **WHEN** Depth Symmetry 使用默认方向校准
- **THEN** 对称前的 canonical 镜像轴 SHALL 为 Y

### Requirement: Cutout node assets no longer expose Depth Axis

`O Image Cutout` 与 `O Image Depth Cutout` MUST 不再公开 `Depth Axis` 输入，并且 MUST 不包含把最终几何从 -Z 转到 +X 的旧轴向旋转。

#### Scenario: Inspect Cutout interfaces

- **WHEN** 检查 `O Image Cutout` 和 `O Image Depth Cutout` 的输入接口
- **THEN** 不存在名为 `Depth Axis` 的 socket
- **AND** 节点组内不存在旧 `CUTOUT_Z_TO_X` 最终旋转
