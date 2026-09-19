# separate-depth-relief-planes Specification

## Purpose
TBD - created by archiving change split-depth-and-relief-planes. Update Purpose after archive.
## Requirements
### Requirement: Independent conversion entries and assets
系统 SHALL 提供 Convert to Depth Plane 和 Convert to Relief Plane 两个入口，分别加载 `O Image Depth Plane` 与 `O Image Relief Plane`。Depth Plane MUST 使用相机投影，Relief Plane MUST 使用固定底面浮雕。两组 SHALL 提供各自参数并移除 Mode 选择。

#### Scenario: Convert an image to a depth plane
- **WHEN** 用户对静态 Image Empty 执行 Convert to Depth Plane
- **THEN** 系统创建相机投影曲面，绑定独立 Depth Plane 节点组，并保留原图构图、UV 与世界位置

#### Scenario: Convert an image to a relief plane
- **WHEN** 用户对静态 Image Empty 执行 Convert to Relief Plane
- **THEN** 系统创建固定底面浮雕，绑定独立 Relief Plane 节点组，Thickness 与 Depth Scale 延续原 Relief 语义

#### Scenario: Inspect modifier controls
- **WHEN** 用户查看两种结果的修改器
- **THEN** 两者各自提供 Subdivide、Thickness、Depth Scale、Reference Depth，Depth Plane 提供 Normal Smooth，两者均无 Mode 选择

### Requirement: Normal space follows conversion type
系统 SHALL 为 Depth Plane 生成并消费 `object_normal`，材质使用 OBJECT 空间；为 Relief Plane 生成并消费 `tangent_normal`，材质使用 TANGENT 空间。法线编码 MUST 与对应对象局部坐标一致。

#### Scenario: Depth material uses object normals
- **WHEN** Depth Plane Job 完成并创建材质
- **THEN** 材质加载 Object Normal 产物并启用 Object Space，法线轴向与相机投影后的局部几何一致

#### Scenario: Relief material uses tangent normals
- **WHEN** Relief Plane Job 完成并创建材质
- **THEN** 材质加载 Tangent Normal 产物并使用 Tangent Space

### Requirement: Shared conversion lifecycle
两个转换 SHALL 使用静态图与 AI 就绪检查、统一深度产物协议、对象替换及失败清理流程。新增 Operator MUST 纳入注册与逆序注销。

#### Scenario: Failed result creation
- **WHEN** 任一转换在加载产物或创建对象时失败
- **THEN** 系统保留可用源对象，并清理本次创建且未被使用的数据块

#### Scenario: Extension lifecycle
- **WHEN** 扩展注册后逆序注销
- **THEN** 两个转换入口均正确注册与移除

### Requirement: Depth plane shares Cutout smoothing
Depth Plane SHALL 在投影与厚度之后复用 Depth Cutout 的 Smooth 模块。Smooth MUST 默认 0、范围 0–20；Options 中的 Smooth Weight MUST 默认 1、范围 0–1，使用 FACTOR 子类型。

#### Scenario: Smooth final geometry
- **WHEN** 用户增加 Smooth 并使用正 Smooth Weight
- **THEN** 最终顶点位置按 Cutout 的共用规则平滑，面连接与 UV 保持一致

#### Scenario: Disable smoothing
- **WHEN** Smooth 为 0 或 Smooth Weight 为 0
- **THEN** 几何位置与未平滑结果相同

