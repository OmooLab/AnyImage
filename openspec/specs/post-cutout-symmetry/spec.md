# post-cutout-symmetry Specification

## Purpose
TBD - created by archiving change compose-depth-cutout-symmetry. Update Purpose after archive.
## Requirements
### Requirement: 原入口串联 Cutout 与对称节点

系统 SHALL 保留 Depth Solid 与 Depth Symmetry 入口。Depth Symmetry SHALL 按顺序创建 `O Image Depth Cutout` 和 `O Image Cutout Symmetry` 修改器，将 Cutout 两种 Thickness 输入均初始化为 0，并分别将深度标定参数与对称方向交给对应节点。

#### Scenario: 创建默认对称对象
- **WHEN** 用户通过原 Depth Symmetry 入口完成轮廓创建
- **THEN** 对象先执行零厚度 Cutout，再执行对称；Cutout 保留节点默认参数，包括 Depth Split、Boundary Smooth、Smooth 与 Depth Axis，仅沿用通用的手势模式选择、清理阈值和图像标定输入
- **AND** 切换 Balloon / Shell 后厚度仍为 0

### Requirement: 节点厚度默认值与入口初始化

`O Image Depth Cutout` 节点资产的 Balloon / Shell 两种 Thickness 默认值 SHALL 均为 0。Depth Solid 创建时 SHALL 按输入 subtype 分别设置 Balloon Thickness 为 1、Shell Thickness 为 0.2，其他创建默认设置保持不变；Depth Symmetry SHALL 使用两种厚度的零默认值。

#### Scenario: 手动添加 Cutout 节点
- **WHEN** 用户从资产添加未经入口覆写的 Cutout 节点
- **THEN** Balloon / Shell 两种 Thickness 均为 0

#### Scenario: 创建 Depth Solid
- **WHEN** 用户通过 Depth Solid 入口创建对象
- **THEN** Balloon Thickness 为 1，Shell Thickness 为 0.2，两个输入均完成初始化
- **AND** 切换模式时使用对应厚度值，边界平滑等其他默认设置保持不变

### Requirement: 成形后镜像与补面

对称节点 SHALL 接收上游完整几何，沿用原 Projected 的方向对齐、偏移、负侧面移除、镜像翻面与对应边界直壁连接语义。Fill Sides SHALL 控制是否添加连接侧壁。

#### Scenario: 非零厚度的两种成形结果
- **WHEN** Balloon 或 Shell 的非零厚度输出连接至对称节点
- **THEN** 节点对已成形结果执行对称；Shell 的壳体内外表面一同参与
- **AND** Fill Sides 关闭时不添加连接壁，开启时连接对应边界且保持面方向一致

### Requirement: 精简对称控制

对称节点 SHALL 仅公开 Geometry、Symmetry Direction、Depth Offset、Fill Sides、Fill Smooth 输入及 Geometry 输出，始终生成镜像两侧。默认方向 SHALL 为 (0, 0, 1)，偏移 SHALL 为 0，Fill Smooth SHALL 为 2，Fill Sides SHALL 开启。

#### Scenario: 默认补面平滑
- **WHEN** 从资产加载新的对称节点
- **THEN** Fill Smooth 默认为 2

#### Scenario: 调整对称方向
- **WHEN** 用户调整 Symmetry Direction 和 Depth Offset
- **THEN** 几何使用原方向对齐及轴向偏移语义更新，对称平面位于调整后的局部 XY 平面
- **AND** 界面不提供 Double Sided、Depth Axis、全局 Smooth 或 Boundary Smooth

### Requirement: 深度 Cutout 使用 Object Space 法线

Depth Solid 与 Depth Symmetry SHALL 使用 Object Space 法线贴图，并在创建材质时开启 `O Image Layer` 的 Object Space。

#### Scenario: 创建深度 Cutout 材质
- **WHEN** 用户通过任一深度 Cutout 入口生成对象
- **THEN** 生成流程请求并读取 object_normal，材质的 Object Space 为开启状态

### Requirement: 仅平滑新增侧壁

Fill Smooth SHALL 控制新增侧壁的几何平滑，固定与保留输入几何相接的端点并保持镜像对称；数值为 0 SHALL 使用原直壁构成。

#### Scenario: 平滑连接壁
- **WHEN** Fill Sides 开启且 Fill Smooth 大于 0
- **THEN** 有曲率的轮廓所生成侧壁内部顶点可被平滑移动，原保留表面及接缝端点不受该平滑移动
- **AND** 对应连接保持封闭，镜像对称关系保持成立

#### Scenario: 禁用补面
- **WHEN** Fill Sides 关闭而 Fill Smooth 改变
- **THEN** 输出几何保持一致

### Requirement: 零厚度匹配原 Projected

在相同输入、标定与方向偏移、相同预处理条件下，Cutout 零厚度接对称节点 SHALL 与原 Depth Symmetry 的 Projected 在顶点位置、面连接及朝向上等价。

#### Scenario: 两种模式与补面开关的一致性
- **WHEN** 分别选择 Balloon / Shell 且两个厚度均为 0，Cutout 分割与平滑关闭、Depth Axis 为 -Z，旧 Projected 的 Smooth 与 Boundary Smooth 为 0，新 Fill Smooth 为 0
- **THEN** 对 Fill Sides 开关分别比较，新旧结果的顶点位置在浮点容差内一致，面数、连接及朝向一致

