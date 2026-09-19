# image-depth-symmetry Specification

## Purpose
TBD - created by archiving change add-projected-depth-symmetry. Update Purpose after archive.
## Requirements
### Requirement: Unified depth symmetry identity
系统 SHALL 使用菜单名称 `Depth Symmetry`、节点组名称 `O Image Depth Symmetry` 和 Shape 标识 `DEPTH_SYMMETRY`，节点 Mode SHALL 按 `Balloon / Projected` 顺序提供选择。

#### Scenario: Load the node asset
- **WHEN** 用户创建 Depth Symmetry 对象
- **THEN** 系统从节点资产加载 `O Image Depth Symmetry`，Mode 包含 Balloon 和 Projected

### Requirement: Gesture selects the initial mode
系统 SHALL 为 Lasso 创建结果选择 Balloon，为 Polyline 创建结果选择 Projected，并允许用户随后手动切换 Mode。

#### Scenario: Lasso preset
- **WHEN** 用户通过 Lasso 选择区域并创建 Depth Symmetry
- **THEN** Mode 初始值为 Balloon

#### Scenario: Polyline preset
- **WHEN** 用户通过 Polyline 选择区域并创建 Depth Symmetry
- **THEN** Mode 初始值为 Projected，Depth Cutout 自身的 Polyline → Shell 关系保持不变

#### Scenario: Switch the generated object's mode
- **WHEN** 用户修改已创建对象的 Mode
- **THEN** 同一份输入网格和深度数据按所选模式重新求值，不受创建手势锁定

### Requirement: Preserve balloon behavior
Balloon 模式 SHALL 保持原 Depth Balloon 的几何与参数行为，在对称平面向原 Cutout 剪影收拢。

#### Scenario: Compare the original mode
- **WHEN** 同一输入、深度图和原有参数分别进入旧基准与新节点的 Balloon 模式
- **THEN** 输出拓扑和位置在浮点容差内一致，包括 Double Sided、Thickness、平滑及 Depth Axis 的行为

### Requirement: Projected positive surface
Projected 模式 SHALL 独立读取深度，使用 Reference Depth 和 Depth Direction 调整正面的置换与投射方向。成形坐标中的正面 MUST 保持在 `Z≥0`，越界面 SHALL 被删除。

#### Scenario: Adjust both depth controls
- **WHEN** 用户修改 Reference Depth 或 Depth Direction
- **THEN** 正面形体与投射轮廓重新求值，镜像平面保持在成形坐标的 `Z=0`

#### Scenario: A face crosses the plane
- **WHEN** 正面某个面含有负 Z 顶点
- **THEN** 该面及失去面支撑的边线、孤点被删除，剩余结果不包含越界正面或外围压平裙边

#### Scenario: Everything is outside
- **WHEN** 参数使全部输入面越界
- **THEN** 输出为空几何，求值正常结束

### Requirement: Close the projected symmetric volume with straight walls
Projected 开启 Double Sided 时 SHALL 关于成形坐标 `Z=0` 镜像，并沿 Z 轴直线连接对应外边界，生成封闭网格。正面平滑 SHALL 在镜像补壁之前完成。

#### Scenario: Complete a car volume
- **WHEN** 合法正面存在外边界且 Double Sided 打开
- **THEN** 输出网格没有开放边、异常面邻接或顶点非流形，面绕序一致；每个 `(x,y,z)` 存在镜像对应点 `(x,y,-z)`

#### Scenario: Check straight walls after smoothing
- **WHEN** 用户开启 Projected 平滑后生成双面网格
- **THEN** 外边界仍沿 Z 轴直线连接，侧壁法线与 Z 轴垂直，平滑不使侧壁弯曲

#### Scenario: Preview only the front
- **WHEN** 用户关闭 Projected 的 Double Sided
- **THEN** 仅输出非负 Z 正面，用于检查投射和裁去区域

### Requirement: Direct node construction and shared builders
Projected 分支 MUST 直接使用基础节点与公共构建函数，不得使用 Mesh Boolean、Capture Attribute 或依赖 Depth Plane、Depth Cutout 节点组。插件运行时 SHALL 从资产加载节点组。

#### Scenario: Inspect the built asset
- **WHEN** 构建与检查 `O Image Depth Symmetry`
- **THEN** 新模式不存在布尔、Capture Attribute 或上述节点组依赖，Depth Symmetry 源码与资产接口一致

### Requirement: Verify performance on equivalent inputs
实现 SHALL 在同一机器、同输入、同平滑和同参数序列下，对比直接构建版本与已验证的布尔原型，分别记录 Reference Depth 和 Depth Direction 更新耗时。

#### Scenario: Compare ordinary and dense meshes
- **WHEN** 对普通与加密网格执行预热后的重复求值
- **THEN** 报告两种更新的中位数、输入规模与测试条件，并确认正式双模式 Projected 分支的求值收益，而非以固定毫秒值作为跨机器测试门槛

