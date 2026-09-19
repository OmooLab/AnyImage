# panorama-mask-regions Specification

## Purpose
TBD - created by archiving change separate-panorama-mask-regions. Update Purpose after archive.
## Requirements
### Requirement: Mask Threshold 按面分出两个区域

`O Image Depth Panorama` MUST 用 Separate Geometry（Face 域）把球面网格按 Mask Threshold 分成两个区域：面中心采样低于 Mask Threshold 的面由 `Selection` 输出，其余面由 `Inverted` 输出。判定 MUST 复用同一次 Mask Threshold 比较，MUST NOT 另行采样或按深度通道判断；分面后 MUST NOT 再单独清理残留边。

#### Scenario: 切口落在面中心轮廓

- **WHEN** 无效区与有效区之间存在只跨过部分顶点的面
- **THEN** 该面在面中心仍有效时留在高 mask 区域，轮廓落在面中心的连线上，而不是所有相邻顶点都有效的内圈

#### Scenario: 两个区域互补

- **WHEN** 任意 mask 图下求值
- **THEN** 两个区域的面数之和等于输入球面的面数，各区域输出的边都至少属于一个面

### Requirement: Depth Mask 打开时只输出高 mask 区域

Depth Mask 打开时，`O Image Depth Panorama` MUST 只输出高 mask 区域经过完整深度处理的几何，低 mask 区域 MUST NOT 出现在输出中；输出 MUST 与按面删除低 mask 面后的处理结果等价。

#### Scenario: 打开时与按面删除等价

- **WHEN** Depth Mask 打开
- **THEN** 输出的面、顶点坐标与 UV 同按面删除低 mask 面后处理的结果一致

#### Scenario: 全部低于阈值

- **WHEN** Depth Mask 打开且所有面中心的采样都低于 Mask Threshold
- **THEN** 输出为空几何

### Requirement: Depth Mask 关闭时两区域分别处理再合并

Depth Mask 关闭时，低 mask 区域 MUST 保持自身方向、整片位移到 `Dome Radius` 球面，高 mask 区域 MUST 照常做 Depth Split、径向深度重建与切口带平滑，两者 MUST 在各自处理完成后 Join 成同一输出。低 mask 区域 MUST NOT 参与 Depth Split 与深度边界模糊，但 MUST 与高 mask 区域一样在自身自由边界上按 Boundary Smooth 松弛；输出 MUST NOT 跨区域焊接或平均顶点。

#### Scenario: 两个区域各自落位

- **WHEN** Depth Mask 关闭，且 mask 图同时含高、低两个区域
- **THEN** 高 mask 区域各点半径等于 `Dome Radius + Depth Scale × (d − Dome Radius)`，低 mask 区域各点半径等于 `Dome Radius`

#### Scenario: 低 mask 区域的采样深度不影响输出

- **WHEN** Depth Mask 关闭，且低 mask 区域写入与有效侧相差一个数量级的深度
- **THEN** 该区域仍整片落在 `Dome Radius` 球面上

#### Scenario: Depth Scale 为 0

- **WHEN** Depth Scale 为 0 且 Depth Mask 关闭
- **THEN** 两个区域都落在半径为 `Dome Radius` 的球面上，输出仍是完整球面

#### Scenario: 接缝两侧不共享顶点

- **WHEN** Depth Mask 关闭，且 mask 图同时含高、低两个区域
- **THEN** 接缝两侧各自保留自己的顶点，接缝在两侧都是自由边，输出顶点数多于同一网格不分面时的顶点数

#### Scenario: 两侧边界都随 Boundary Smooth 松弛

- **WHEN** Depth Mask 关闭且 Boundary Smooth 大于 0
- **THEN** 低 mask 区域接缝带内的点与高 mask 区域接缝带内的点都移动，两个区域的内部点保持不变，低 mask 区域的内部点仍落在 `Dome Radius` 球面上

### Requirement: Depth Scale 为 0 且 Depth Mask 关闭时输出整球

Depth Scale 为 0 且 Depth Mask 关闭时，`O Image Depth Panorama` MUST 直接输出半径为 `Dome Radius` 的完整球面，MUST NOT 做分面、Depth Split、切口带平滑，也 MUST NOT 留下未共享的接缝顶点；输出 MUST 是封闭网格。Depth Mask 打开时 MUST NOT 走这条旁路。

#### Scenario: 关闭开关的平坦投影没有切线

- **WHEN** Depth Scale 为 0 且 Depth Mask 关闭
- **THEN** 输出的面数与顶点数与同一球面的完整网格一致，没有自由边，各点半径等于 `Dome Radius`

#### Scenario: 打开开关的平坦投影仍按 mask 排除

- **WHEN** Depth Scale 为 0 且 Depth Mask 打开
- **THEN** 输出只含高 mask 区域，低 mask 区域不出现

### Requirement: 高 mask 区域沿用既有切口与深度语义

Separate Geometry 形成的自由边界 MUST 继续走既有切口规则：深度取相邻面采样，点保持自身射线方向。Depth Split、Depth Scale、UV 与材质槽继承 MUST 保持既有职责，`O Image Depth Plane` 的 Depth Mask 删除行为 MUST 保持不变。

#### Scenario: 打开开关时切口不出现尖刺

- **WHEN** Depth Mask 打开，且低 mask 侧采样与有效侧相差一个数量级
- **THEN** 切口圈各点的径向距离等于相邻有效面中心的采样距离

#### Scenario: 关闭开关时高 mask 区域仍按切口规则处理

- **WHEN** Depth Mask 关闭且 Boundary Smooth 为 0
- **THEN** 高 mask 区域的接缝点深度取相邻面采样，不跟随低 mask 侧的采样

#### Scenario: Plane 不受影响

- **WHEN** `O Image Depth Plane` 用同一深度图求值，Depth Mask 打开或关闭
- **THEN** 输出与本次改动前逐位一致

