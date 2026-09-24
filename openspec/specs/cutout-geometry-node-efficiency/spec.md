# cutout-geometry-node-efficiency Specification

## Purpose
TBD - created by archiving change optimize-cutout-geometry-nodes. Update Purpose after archive.
## Requirements
### Requirement: Depth Cutout reuses the projected outline field

`O Image Depth Cutout` SHALL calculate the POINT/BOOLEAN outline field once on the post-split, pre-projection topology and reuse it for boundary-sensitive consumers on the same topology after projection. It SHALL NOT create separate Edge Neighbors and Vertex Neighbors fields for each consumer in the same topology stage.

#### Scenario: Same topology boundary consumers share the field

- **WHEN** Depth Cutout builds volume fields, original boundary sampling, and boundary smoothing after depth projection
- **THEN** these consumers read the same projected outline field, and the output geometry matches the prior implementation for zero and positive thickness

#### Scenario: Topology changes still receive a fresh boundary field

- **WHEN** Split Edges or boundary triangle cleanup changes topology before projection
- **THEN** the shared outline field is evaluated after that topology change, not reused across the destructive operation

### Requirement: Center field derives from shared low-frequency fields

`O Image Depth Cutout` SHALL compute the smoothed depth and profile fields with the existing 256-iteration interior-weighted blur, and SHALL derive the center field as `depth_slow - profile_slow` instead of running an additional equivalent blur on `depth - profile`.

#### Scenario: Center field is equivalent to the direct blur

- **WHEN** Depth Cutout evaluates a Balloon input with nonzero `o_balloon` and positive Thickness
- **THEN** the derived center values are equal to the prior direct center blur values within floating-point tolerance

#### Scenario: Uniform surface keeps the same center behavior

- **WHEN** Depth Cutout evaluates a zero-profile uniform surface
- **THEN** the derived center field produces the same front and rear positions as the prior implementation

### Requirement: Depth Cutout uses triangle-only strip cleanup

`O Image Depth Cutout` SHALL build only the triangle strip cleanup path because its input is triangulated. It SHALL NOT construct the quad strip cleanup branch used by other depth surfaces.

#### Scenario: Triangular strips are cleaned without quad nodes

- **WHEN** Depth Cutout receives a triangulated cutout mesh with thin boundary strips
- **THEN** strip faces are removed and the remaining geometry matches the prior triangle cleanup result

#### Scenario: Other depth surfaces keep their existing cleanup path

- **WHEN** Depth Plane or Depth Panorama evaluates a quad mesh
- **THEN** their existing quad strip cleanup behavior is unchanged

### Requirement: Zero thickness short-circuits shell construction

Both `O Image Cutout` and `O Image Depth Cutout` SHALL return the original single-surface geometry when the selected thickness input is below the existing zero threshold, without evaluating shell extrusion or thickness field sampling.

#### Scenario: Cutout Balloon and Shell remain single surface at zero

- **WHEN** Mode is Balloon or Shell and the selected Thickness or Shell Thickness is zero
- **THEN** the output is the original Cutout surface with no shell faces, and no thickness-related node warnings occur

#### Scenario: Depth Cutout keeps the projected front at zero thickness

- **WHEN** Depth Cutout has zero selected thickness
- **THEN** the output is the projected front surface, and thickness-only fields and shell geometry are not evaluated

### Requirement: Node graph optimization preserves Cutout geometry

The boundary reuse, center derivation, triangle-only cleanup, and zero-thickness short-circuit SHALL NOT change the finite output geometry, face order, UVMap, or public attributes for supported Cutout and Depth Cutout combinations.

#### Scenario: Representative mode and thickness matrix is equivalent

- **WHEN** Cutout and Depth Cutout are evaluated with Balloon/Shell modes, zero and positive thickness, Depth Split zero and positive, and representative input shapes
- **THEN** vertex positions and face topology are equivalent to the prior implementation within the existing test tolerance

#### Scenario: High-density mesh remains closed with thickness

- **WHEN** Depth Cutout uses a mesh with more than 4096 source vertices and positive thickness
- **THEN** the thickened shell remains finite and closed with no non-manifold boundary

### Requirement: Leaf smoothing uses one shared Repeat Zone

Depth Cutout 正厚度路径 SHALL 把同源 Front 与 pre-flipped Rear 作为断开的 mesh islands 输入一个共同 Boundary Smooth Repeat Zone。零厚度路径 SHALL 经同一平滑入口只输入 Front。最终节点组不得保留第二条 leaf smoothing Repeat Zone。

#### Scenario: 正厚度共同平滑
- **WHEN** Thickness 为正
- **THEN** Front 与 Rear SHALL 共同执行一个 Boundary Smooth Repeat Zone
- **AND** Rear SHALL 在该 Repeat Zone 之前完成 Face-domain 位移、Rear Smooth 和 Flip Faces

#### Scenario: 零厚度复用平滑入口
- **WHEN** Thickness 为零
- **THEN** 共同平滑入口 SHALL 只接收 Front
- **AND** Rear、lookup 与 Wall 不得出现在输出中

### Requirement: Bridge mapping uses linear auxiliary work

Source-index lookup、边界提取与 Wall 生成 SHALL 随点数和边界边数线性增长，不得为每个点或每条边复制节点链、执行全网格 nearest 查询或增加嵌套 Repeat Zone。

#### Scenario: 高密度边界桥接
- **WHEN** Depth Cutout 使用超过 4096 个 source points 的正厚度网格
- **THEN** bridge mapping SHALL 只使用固定数量的字段、排序或采样节点
- **AND** Wall face 数 SHALL 等于 Front boundary edge 数

### Requirement: Depth Cutout 平滑循环不创建边界子网格

`O Image Depth Cutout` 的共享 Boundary Smooth Repeat Zone MUST NOT 包含 Separate Geometry、Sample Nearest 或 Sample Index。边界 Position 与 UV 目标 SHALL 仅通过原网格上的字段和 Blur Attribute 计算。

#### Scenario: 正厚度共同平滑

- **WHEN** Front 与 Rear 共同进入 Boundary Smooth
- **THEN** 每轮在两张断开 leaf 的原拓扑上计算边界目标
- **AND** 不创建临时边界 Geometry

#### Scenario: 输出保持稳定

- **WHEN** Depth Cutout 使用零或正厚度、零或正 Boundary Smooth
- **THEN** 输出 Position、UV、拓扑、闭合性与公开属性保持既有行为

### Requirement: Depth Cutout 跳过禁用控制对应的昂贵字段

`O Image Depth Cutout` SHALL 通过 Geometry Switch 让禁用的平滑或厚度分支保持惰性求值。

#### Scenario: 零 Boundary Smooth

- **WHEN** Boundary Smooth 为零
- **THEN** 不计算或存储边界平滑权重

#### Scenario: 零厚度

- **WHEN** 当前模式的 Thickness 为零
- **THEN** 不计算或存储 256 次 Blur 产生的 front normal direction

### Requirement: Depth Cutout 不计算动态焊接距离

`O Image Depth Cutout` MUST NOT 在投影后执行 CONNECTED Merge by Distance，并 SHALL 将最终 ALL Merge by Distance 的 Distance 固定为 `1e-6`，不得从边长统计计算焊接距离。

#### Scenario: 正厚度输出

- **WHEN** Front、Rear 与 Side 合并为最终实体
- **THEN** 仅执行一次 ALL Merge by Distance
- **AND** Distance 输入不连接字段且值为 `1e-6`

