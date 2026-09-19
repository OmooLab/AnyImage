# projected-depth-surface Specification

## Purpose
TBD - created by archiving change add-projected-depth-plane. Update Purpose after archive.
## Requirements
### Requirement: Full-image depth surface has a conversion entry
系统 SHALL 提供 `anyimage.convert_to_depth_surface`，界面显示 Convert to Depth Surface，与 Plane、Depth Plane 并列；该入口 SHALL 从当前静态 Image Empty 创建完整图片的相机投影曲面。

#### Scenario: Convert a still image
- **WHEN** 当前 Image Empty 是静态图片且 AI 环境可用
- **THEN** 执行一次完整图片转换，成功后结果沿用源对象名称并替换源 Empty
- **AND** 一次 Undo 恢复转换前状态

#### Scenario: Reject unsupported media
- **WHEN** 输入为多帧 Movie 或 Sequence
- **THEN** 提示仅支持静态图片，不提交推理任务

#### Scenario: AI setup is required
- **WHEN** AI 环境未就绪
- **THEN** 沿用现有 AI 设置流程，源 Empty 保持可用

### Requirement: Base geometry matches Plane conversion
Depth Surface SHALL 使用普通 Convert to Plane 的基础 Mesh 创建、中心矩阵、UV 和 O Mesh Plane 细分。相同 Subdivide 下投影前零厚度几何 MUST 与普通 Plane 的零厚度几何一致。整图矩形拓扑 SHALL 覆盖透明区域及深度跳变区域。

#### Scenario: Compare planar meshes
- **WHEN** 对同一图片以相同 Subdivide 创建普通 Plane 和 Thickness 0、Depth Scale 0 的 Depth Surface
- **THEN** 两者顶点位置、面连接、UV 和材质索引一致

#### Scenario: Preserve placement
- **WHEN** 源 Image Empty 具有非中心显示偏移以及平移、旋转、缩放
- **THEN** Depth Scale 0、Thickness 0 的结果四角与源显示矩形的世界空间四角一致
- **AND** 对象原点位于显示矩形中心

#### Scenario: Preserve rectangular coverage
- **WHEN** 图片包含透明孔洞或纹理深度跳变
- **THEN** 基础网格仍为完整矩形细分，Alpha 由材质表达

### Requirement: Surface controls include normal smoothing
`O Image Depth Surface` SHALL 只公开 Subdivide、Thickness、Depth Scale、Reference Depth 以及 Normal Smooth 五项用户控制。默认值 SHALL 分别为 6、0、1 和 Metadata reference_depth 乘以 Uniform Scale。Geometry SHALL 为结构输入，Depth Image 与 Uniform Scale SHALL 为隐藏数据输入。输入 MUST 使用 SINGLE；Thickness、Reference Depth MUST 使用 DISTANCE。

#### Scenario: Inspect a new modifier
- **WHEN** 创建 Depth Surface 修改器
- **THEN** 用户看到规定的五项控制，Reference Depth 与 Normal Smooth 位于 Options；Normal Smooth 默认 50，范围 0–50
- **AND** 不出现 Cutout 的 Mode、Split、Balloon、Inflation、轮廓或轴向控制

### Requirement: Geometry follows camera projection
Depth Surface SHALL 按现有 Depth Cutout 的相机 XYZ 坐标约定投影。采样 XYZ 乘以 Uniform Scale 后，XY SHALL 以 Depth Scale 从基础平面插值至相机 X、负相机 Y；Z SHALL 为 `(Reference Depth − scaled_camera_z) × Depth Scale`。

#### Scenario: Full projection
- **WHEN** Thickness 为 0、Depth Scale 为 1，输入合成相机 XYZ 纹理
- **THEN** 每个顶点的位置符合相机投影公式，包括 Y 方向与深度基准

#### Scenario: Adjust depth strength
- **WHEN** Depth Scale 分别为 0、0.5、1 和大于 1 的值
- **THEN** XY 与 Z 按同一缩放语义连续变化，0 恢复基础平面，大于 1 正常外推

#### Scenario: Adjust reference depth
- **WHEN** Reference Depth 增加局部距离 d，Depth Scale 为 s
- **THEN** 曲面 Z 增加 d × s，投影 XY 保持不变

### Requirement: Thickness forms a uniform surface shell
Thickness 为 0 时系统 SHALL 输出单层曲面；Thickness 大于 0 时 SHALL 保留投影正面，按正面 POINT 法线按 Normal Smooth 进行邻域平滑并归一化后的方向向内生成背面并连接矩形边界。

#### Scenario: Zero thickness
- **WHEN** Thickness 为 0
- **THEN** 仅存在一层曲面，无重复背面或退化侧壁

#### Scenario: Positive thickness
- **WHEN** 对平坦深度输入设置正 Thickness
- **THEN** 对应正背面顶点之间的距离等于 Thickness，边界闭合且法线朝向一致

### Requirement: One prediction produces complete image artifacts
整图 Depth Surface SHALL 通过共用 Artifact 层执行一次 MoGe-2 推理，生成 VECTOR Depth、Metadata 与 Tangent Normal，并保留完整 Color。Blender SHALL 在主线程加载、Pack 并设置图片色彩空间，将 Normal 用于材质，将 VECTOR Depth 用于几何。

#### Scenario: Complete a generation job
- **WHEN** 整图 Depth Surface Job 成功
- **THEN** 只执行一次推理，并返回 `vector_depth`、`depth_metadata`、`tangent_normal` 及完整颜色产物

#### Scenario: Preserve existing depth plane generation
- **WHEN** 用户执行现有 Convert to Depth Plane
- **THEN** 继续生成 Z Depth 与 Tangent Normal，并创建固定底面浮雕

### Requirement: Node assets preserve geometry data
新节点组 SHALL 从 `assets/O_AnyImage.blend` 按名称加载。节点求值 SHALL 保留 UV 与第 0 个材质槽，并清理自身临时属性；构建验证 SHALL 检查接口、实际几何与 Blender 中的节点布局。

#### Scenario: Evaluate the asset
- **WHEN** 加载并求值 `O Image Depth Surface`
- **THEN** 结果保留 UV、用户属性和材质，不残留自身 `o_depth_*` 临时属性

