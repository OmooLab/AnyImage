## ADDED Requirements

### Requirement: Cutout base mesh matches the source image plane
系统 SHALL 直接在源 Image Empty 的局部 XY 平面创建 Cutout BaseShape，基础顶点 MUST 使用 `z = 0`，逆时针正面 MUST 朝局部 `+Z`，且对象放置 MUST 保持裁切区域的世界空间位置。

#### Scenario: Inspect a Cutout before Geometry Nodes evaluation
- **WHEN** 系统已从源图片裁切区域创建 Cutout Mesh，但尚未求值或复用 `O Image Cutout` Modifier
- **THEN** Mesh 位于对象局部 XY 平面，正面朝向与源 Image Empty 一致，且 X/Y 范围对应原裁切区域

#### Scenario: Evaluate an undeformed Surface
- **WHEN** Surface Cutout 以零厚度和零平滑求值
- **THEN** 求值前后的平面内坐标、正面朝向和世界空间位置保持一致，不执行轴交换或补偿旋转

### Requirement: Cutout Shape nodes use the local Z axis
`O Image Surface`、`O Image Balloon`、`O Image Depth Balloon` 与 `O Image Depth Surface` SHALL 接收局部 XY 平面几何，并统一使用局部 `-Z` 表示从图片平面向内的方向。外层 `O Image Cutout` 的默认 `-Z` 分支 MUST 直通该原生结果。平面内 X/Y 坐标 MUST 不因 Shape 求值而互换。

#### Scenario: Reuse a Shape group with XY geometry
- **WHEN** 任一 Cutout Shape 节点组直接接收位于 XY 平面的输入 Mesh
- **THEN** 节点组沿 Z 轴生成 Shape，并保持输入几何的 X/Y 方向

#### Scenario: Build Surface or Balloon thickness
- **WHEN** Surface 或 Balloon 使用正 Thickness 求值
- **THEN** 厚度和 Balloon 高度沿局部 Z 轴展开，图片内部一侧位于负 Z 方向

#### Scenario: Apply depth deformation
- **WHEN** Depth Balloon 或 Depth Surface 使用非零 Depth Scale 求值
- **THEN** 深度位置在统一的 XY / Z 对象空间中计算，不依赖 X 轴中间坐标系或最终轴变换

### Requirement: Cutout exposes selectable output axes
系统 SHALL 保留 **Inward Axis** Scene Property、Operator 参数和 `O Image Cutout` 节点接口。`-Z` MUST 为默认值并直接使用原生 XY / Z Shape 结果；选择 `+X` 时，外层节点组 MUST 将 Z 轴结果转换为 `+X` 内向对象空间，对象矩阵 MUST 执行配对补偿以保持相同世界空间形状。

#### Scenario: Create a Cutout from the tool
- **WHEN** 用户打开 Cutout 工具设置并选择任一 Shape
- **THEN** 工具显示并传递 **Inward Axis**，默认 `-Z` 创建结果直接沿用源 Image Empty 的局部轴

#### Scenario: Select the positive X output
- **WHEN** 用户把 **Inward Axis** 设为 `+X`
- **THEN** `O Image Cutout` 将原生 Z 轴 Shape 转换为 `+X` 内向的局部几何，对象矩阵同步补偿，世界空间位置和外观与默认结果一致

#### Scenario: Reuse a Shape subgroup directly
- **WHEN** 调用方绕过外层 `O Image Cutout` 并直接复用任一 Shape 子节点组
- **THEN** 子节点组始终使用原生 XY / Z 坐标，不公开或模拟旧 X 轴内部约定

### Requirement: Depth Surface normals match the Z-axis object space
Depth Surface 的 Object Space Normal Artifact SHALL 编码原生 Z 轴 Cutout 对象空间；不可见区域 MUST 使用局部 `+Z` 中性法线。默认 `-Z` 输出 MUST 原样使用该图片；选择 `+X` 输出时，Blender MUST 将其转换到配对的 `+X` 对象空间。

#### Scenario: Encode a known object-space normal
- **WHEN** Server 为 Depth Surface 编码已知的相机空间法线
- **THEN** 输出通道直接对应最终 XY / Z Cutout 对象空间，且无需 Blender 后处理即可作为 Object Space Normal 使用

#### Scenario: Load a Depth Surface normal image
- **WHEN** Blender 收到 `object-normal.png` 并以默认 `-Z` 创建 Depth Surface 材质
- **THEN** 图片像素保持 Artifact 原值并以 Object Space 连接到材质

#### Scenario: Load a positive X Depth Surface normal image
- **WHEN** Blender 收到 `object-normal.png` 并以 `+X` 创建 Depth Surface 材质
- **THEN** 图片通道按 Z 到 X 的配对轴变换转换一次，再以 Object Space 连接到材质

#### Scenario: Fill an invisible normal region
- **WHEN** Object Space Normal 的像素不在可见内容区域
- **THEN** 该像素编码局部 `+Z`，不会在正面产生虚假的侧向法线
