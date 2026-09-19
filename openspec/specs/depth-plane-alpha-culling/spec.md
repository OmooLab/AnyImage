# depth-plane-alpha-culling Specification

## Purpose
TBD - created by archiving change split-depth-and-relief-planes. Update Purpose after archive.
## Requirements
### Requirement: Optional alpha culling defaults to enabled
Depth Plane 修改器 SHALL 提供默认开启的 Valid Only 开关，按 depth.exr 有效性 Alpha 剔除几何。该处理 MUST 在基础网格细分之后、深度投影和厚度之前执行。

#### Scenario: Default conversion
- **WHEN** 用户转换包含无效深度区域的图片为 Depth Plane
- **THEN** Valid Only 默认开启，深度有效性 Alpha 参与基础网格的几何剔除

#### Scenario: Disable alpha culling
- **WHEN** 用户关闭 Valid Only
- **THEN** 完整细分网格进入相机投影与厚度流程

#### Scenario: Fully valid depth
- **WHEN** depth.exr 有效性 Alpha 全部为 1
- **THEN** Alpha 剔除保留完整基础网格

### Requirement: Culling remains responsive to subdivision
系统 SHALL 在节点内重新求值 Alpha 剔除，允许用户继续通过 Subdivide 调节网格。剔除后的几何 MUST 保留正确 UV，并进入现有相机投影和曲面厚度计算。

#### Scenario: Change subdivision
- **WHEN** 用户修改 Subdivide
- **THEN** 节点重新生成网格并依据该网格重新检测 Alpha，无需重新运行 AI

#### Scenario: Apply thickness after culling
- **WHEN** 用户对已剔除的曲面设置正 Thickness
- **THEN** 厚度从保留的曲面生成，无效区域已删除的基础面不会重新出现

### Requirement: Permissive culling follows the reference graph
Alpha 剔除 MUST 使用用户参考图中的宽松判定连接，且只公开 Valid Only 开关，网格精度使用已有 Subdivide。

深度图片 SHALL 使用 Linear / Extend 采样；Separate Color 的 Alpha SHALL 接 Float / Less Than（B = 1），结果通过 Boolean / Point 的 Evaluate on Domain 后接 Delete Geometry（Face、All）。一个面仅在所有顶点都满足 Alpha < 1 时删除；至少一个顶点 Alpha 为 1 的边界面保留。

#### Scenario: Verify the reference rule
- **WHEN** 实现 Alpha 判定
- **THEN** 节点连接、运算、默认值和域设置与参考图一致，有效与无效区域交界网格的保留结果符合该图规则

