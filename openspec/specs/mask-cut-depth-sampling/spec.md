# mask-cut-depth-sampling Specification

## Purpose
TBD - created by archiving change unify-mask-cut-depth. Update Purpose after archive.
## Requirements
### Requirement: 自由边界与切边取相邻面的深度采样

`O Image Depth Plane` 与 `O Image Depth Panorama` 上由 Depth Mask 删除产生的切口点，以及 `O Image Depth Plane` 原画幅外框上的点，其深度 MUST 取该点相邻保留面的采样值，而不是该点自己的纹理采样。切口点 MUST 保持自身的射线方向，只改变沿射线的深度分量。

#### Scenario: 无效侧深度尖刺不影响 Plane 切口

- **WHEN** Depth Mask 删除一片区域，且紧邻该区域的无效侧像素深度与有效侧相差一个数量级
- **THEN** 切口点的深度等于相邻有效面中心的采样深度，切口不出现跟随无效侧像素的尖刺

#### Scenario: Panorama 切口跟随有效侧半径

- **WHEN** Panorama 的 Depth Mask 删除一片区域，且被删区域的距离值与有效侧相差一个数量级
- **THEN** 切口圈各点的径向距离等于相邻有效面中心的采样距离

#### Scenario: 射线方向保持

- **WHEN** 切口点取相邻面深度
- **THEN** Plane 切口点的相机横纵坐标不变，Panorama 切口点仍落在原经纬方向上

#### Scenario: 关闭 Depth Split 时仍然生效

- **WHEN** Depth Split 为 0
- **THEN** 切口点仍取相邻面深度，Depth Split 切边不参与深度替换

#### Scenario: 外框与切口同规则

- **WHEN** `O Image Depth Plane` 用同一深度图求值，Depth Mask 打开或关闭
- **THEN** 原画幅外框上的点与外框邻接面的采样深度一致，不保留自身采样

### Requirement: 切口规则内建在共享相机采样

切口规则 MUST 由 `build_surface_camera` 自身求值自由边界并应用，调用方 MUST NOT 传入「哪些点使用面深」的集合，也 MUST NOT 传入排除字段；Depth Split 切边 MUST 与切口点走同一条深度替换路径。

#### Scenario: 三个调用点行为一致

- **WHEN** 比较 `O Image Depth Cutout`、`O Image Depth Plane` 与 `O Image Depth Panorama` 的相机采样接线
- **THEN** 三者都不传入点集合或排除字段，切口点与 Depth Split 切边由同一规则覆盖

### Requirement: Depth Mask 按面删除

Depth Mask 的删除 MUST 按面判定：面中心的采样低于 Mask Threshold 时删除该面，其余面连同其顶点一起保留。删除后 MUST NOT 再单独清理残留边。

#### Scenario: 切口不再多退一圈

- **WHEN** Depth Mask 打开，且无效区与有效区之间存在只跨过部分顶点的面
- **THEN** 该面在面中心仍有效时保留，切口落在面中心轮廓上，而不是所有相邻顶点都有效的内圈

#### Scenario: 删除后没有悬空边

- **WHEN** Depth Mask 删除整片面
- **THEN** 输出的边都至少属于一个保留面，没有只由删除残留形成的边

### Requirement: Panorama 的无效面落到 Dome Radius

`O Image Depth Panorama` 的 `Dome Radius` MUST 同时承担两个作用：Depth Scale 为 0 时的球半径，以及 Depth Mask 关闭时被保留的无效面所落到的距离。无效判定 MUST 复用同一次 Mask Threshold 比较，MUST NOT 另行采样或按深度通道判断。输出半径 MUST 为 `Dome Radius + Depth Scale × (d − Dome Radius)`，`d` 为有效点的距离采样。

#### Scenario: 关闭 Depth Mask 保留无效区

- **WHEN** Depth Mask 关闭，且存在 alpha 低于 Mask Threshold 的面
- **THEN** 这些面整片落在 Dome Radius，其余面保持自身距离

#### Scenario: Depth Scale 为 0

- **WHEN** Depth Scale 为 0
- **THEN** 输出是半径为 Dome Radius 的球面

### Requirement: 原画幅外框的平滑保护独立于切口规则

`O Image Depth Plane` 的原画幅外框（UV 边距为 0 的点）MUST 继续作为 `smooth_boundary_camera` 与 `smooth_cut_boundary` 的保护范围，边界带平滑 MUST NOT 因此改变切口规则的覆盖范围。

#### Scenario: 外框保护不参与深度规则

- **WHEN** Boundary Smooth 大于 0 且存在切口
- **THEN** 原画幅外框保持不被边界带平滑拖入，同时其深度仍取相邻面采样

#### Scenario: 关闭 Depth Mask 时几何逐位不变

- **WHEN** Depth Mask 关闭
- **THEN** `O Image Depth Plane` 与 `O Image Depth Panorama` 的输出与改动前逐位一致

### Requirement: 切口深度先锚定后过渡

切口点的面深替换 MUST 发生在切口带深度模糊与位置平滑之前。切口点的最终几何 MUST 由「面深在切口带内模糊一次，再沿射线重建」得到，带外点的位置与深度 MUST 与改动前一致。

#### Scenario: 切口带保留平滑过渡

- **WHEN** Boundary Smooth 大于 0 且存在 mask 切口
- **THEN** 切口带各点沿各自射线过渡到相邻面深，切口带以外的点与 Boundary Smooth 为 0 时逐位一致

### Requirement: 无相邻面的边界点不参与面深替换

切口规则 MUST 在删除无面边（wire edge）之后求值自由边界。没有相邻保留面的点 MUST NOT 进入面深替换，避免深度塌陷到原点。

#### Scenario: 孤立点保持自身深度

- **WHEN** 几何中存在没有相邻面的自由点
- **THEN** 该点保持自身采样深度，输出坐标有限

