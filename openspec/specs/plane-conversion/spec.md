# plane-conversion Specification

## Purpose
TBD - created by archiving change rework-plane-conversion. Update Purpose after archive.
## Requirements
### Requirement: Converted planes use a centered origin
系统 SHALL 让 Convert to Plane 和 Convert to Depth Plane 的结果对象以生成矩形面的中心为对象原点，同时保持源 Image Empty 所表示矩形的世界空间位置不变。

#### Scenario: Convert an offset Image Empty
- **WHEN** 用户转换一个 `empty_image_offset` 不以原点为中心的 Image Empty
- **THEN** 结果对象原点位于矩形面的中心
- **AND** 结果面的四个世界空间角点与转换前 Image Empty 的显示范围一致

#### Scenario: Preserve transformed placement
- **WHEN** 源 Image Empty 带有平移、旋转或缩放
- **THEN** 普通 Plane 和 Depth Plane 均通过对象矩阵保留这些世界空间变换
- **AND** 结果 Mesh 顶点以对象原点为中心分布

### Requirement: Plane node groups retain the Mesh material set
`O Mesh Plane` 和 `O Image Depth Plane` SHALL 不公开 `Material` socket。创建对象的代码 SHALL 把图像材质放入 Mesh 的第 `0` 个材质槽；`O Mesh Plane` SHALL 在删除输入几何前把其材质集合传递给纯生成几何，并让生成面使用材质索引 `0`。

#### Scenario: Evaluate a generated Plane
- **WHEN** 带有第 0 个材质槽的对象通过 `O Mesh Plane` 生成平面或体块
- **THEN** 求值后的 Mesh 保留该材质槽
- **AND** 所有面使用材质索引 `0`
- **AND** Modifier 不包含 `Material` 输入

#### Scenario: Evaluate a generated Depth Plane
- **WHEN** 带有第 0 个材质槽的对象通过 `O Image Depth Plane` 生成地形体块
- **THEN** 求值后的 Mesh 保留该材质槽
- **AND** 所有面使用材质索引 `0`
- **AND** `O Image Depth Plane` 不向 `O Mesh Plane` 传递材质

### Requirement: Depth Plane exposes unified depth controls
`O Image Depth Plane` SHALL 使用 `Thickness`、`Depth Scale`、`Base Plane Depth` 和 `Subdivide` 作为用户控制项。`Depth Image` 与 `Uniform Scale` SHALL 继续作为隐藏数据输入。旧的 `Depth Amount`、`Reference Depth` 和 `Material` 输入 SHALL 不再存在。

#### Scenario: Create a Depth Plane modifier
- **WHEN** Convert to Depth Plane 创建 Modifier
- **THEN** `Depth Scale` 默认值为 `1.0`
- **AND** `Base Plane Depth` 取当前 Depth Metadata 的参考深度乘以 `Uniform Scale`
- **AND** `Subdivide` 默认值为 `6`

#### Scenario: Inspect the node group interface
- **WHEN** 加载发布资产中的 `O Image Depth Plane`
- **THEN** 输入接口包含 `Geometry`、`Subdivide`、`Thickness`、`Depth Scale`、`Base Plane Depth`、`Uniform Scale` 和 `Depth Image`
- **AND** 输入接口不包含 `Depth Amount`、`Reference Depth` 或 `Material`

### Requirement: Depth Plane shares one prediction for depth and material normal
系统 SHALL 让 Depth Plane 通过通用 MoGe-2 Artifact 生成层执行一次模型预测，并从同一个 `GeometryFrame` 生成 `z-depth.exr`、`depth.json` 与 `tangent-normal.png`。Blender SHALL 将 Tangent Normal 作为 Non-Color 图片加载、Pack 并接入结果材质；Normal Map SHALL 只影响材质着色，不参与 Geometry Nodes 置换。

#### Scenario: Generate Depth Plane artifacts
- **WHEN** Depth Plane Job 处理一张完整图片
- **THEN** MoGe-2 inference 只执行一次
- **AND** Job 返回 `z_depth`、`depth_metadata` 和 `tangent_normal`

#### Scenario: Create the Depth Plane material
- **WHEN** Blender 接收成功的 Depth Plane Job 结果
- **THEN** `tangent-normal.png` 以 Non-Color Tangent Space Normal 加载并 Pack
- **AND** 结果材质的 Normal 输入使用该图片
- **AND** 结果材质的 Principled IOR 为 `1.2`
- **AND** `z-depth.exr` 继续单独驱动 Depth Plane 几何置换

#### Scenario: Keep workflow-specific job orchestration
- **WHEN** Depth Plane 与 Cutout 请求 MoGe-2 产物
- **THEN** 两者复用同一个通用 Artifact 生成层
- **AND** Depth Plane Job 不承担 Cutout 的 Selection、Refine Selection 或裁切结果协议

### Requirement: Depth Plane is a single-sided terrain block
系统 SHALL 从 `O Mesh Plane` 的有厚度几何生成 Depth Plane。固定底面 SHALL 位于原图片平面，未置换的可变面 SHALL 位于其正法线方向的 `Thickness` 距离处；只有可变面完整应用深度置换，固定底面 SHALL 完全不动，侧壁中间环 SHALL 按其厚度位置线性渐变置换。

#### Scenario: Disable depth displacement
- **WHEN** `Depth Scale` 为 `0`
- **THEN** 固定底面保持在原图片平面
- **AND** 可变面位于正法线方向的 `Thickness` 距离处

#### Scenario: Change depth displacement
- **WHEN** 用户改变 `Depth Scale` 或 `Base Plane Depth`
- **THEN** 可变面按完整位移变化
- **AND** 固定底面的所有顶点位置保持不变

#### Scenario: Interpolate side-wall rings
- **WHEN** `Thickness` 大于 `0` 且 Depth Plane 发生置换
- **THEN** 侧壁包含位于正面与背面之间的细分环
- **AND** 每个环的位移按其从固定底面到可变面的归一化位置在零位移与完整位移之间线性插值

### Requirement: Depth displacement uses the calibrated zero plane
系统 SHALL 以采样 Z Depth 乘以隐藏的 `Uniform Scale` 得到局部深度，并以 `Base Plane Depth` 为零位移位置。比零平面更近的采样 SHALL 向正法线方向置换，比零平面更远的采样 SHALL 向固定底面置换。

#### Scenario: Sample the base depth
- **WHEN** 某个正面顶点采样的缩放深度等于 `Base Plane Depth`
- **THEN** 该顶点的深度位移为零

#### Scenario: Sample a nearer depth
- **WHEN** 某个正面顶点采样的缩放深度小于 `Base Plane Depth`
- **THEN** 该顶点沿正法线方向产生与 `Depth Scale` 成比例的位移

#### Scenario: Sample a farther depth
- **WHEN** 某个正面顶点采样的缩放深度大于 `Base Plane Depth`
- **THEN** 该顶点向固定底面产生与 `Depth Scale` 成比例的位移

### Requirement: Inward displacement does not cross the fixed base
系统 SHALL 把负向可变面位移限制在固定底面之前，并保留非零间隙以避免可变面、侧壁环和底面折叠或相交。正向位移 SHALL 不受 `Thickness` 限制，因此最终包围盒深度可以大于基础厚度。

#### Scenario: Excessive inward displacement
- **WHEN** 深度公式产生绝对值大于或等于 `Thickness` 的负向位移
- **THEN** 可变面停留在固定底面之前
- **AND** 所有侧壁环仍按顺序位于固定底面与可变面之间

#### Scenario: Outward displacement exceeds the base thickness
- **WHEN** 正向深度位移大于 `Thickness`
- **THEN** 系统保留完整正向位移
- **AND** 固定底面仍位于原图片平面

