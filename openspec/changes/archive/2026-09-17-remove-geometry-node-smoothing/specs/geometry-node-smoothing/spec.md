## ADDED Requirements

### Requirement: 主节点组不得执行末端整体 mesh smooth
系统 SHALL 让 `O Image Cutout`、`O Image Depth Cutout`、`O Image Depth Plane`、`O Image Depth Panorama` 与 `O Image Relief Plane` 在主体几何构建完成后直接进入着色或输出阶段，不得追加由通用 `Smooth` 控制的整体顶点位置平滑。

#### Scenario: 节点组接口不再提供整体 smooth
- **WHEN** 检查任一受影响节点组的公开输入接口
- **THEN** 该接口不包含 `Smooth`

#### Scenario: 输出路径不经过整体 smooth
- **WHEN** 构建任一受影响节点组并追踪其最终业务几何到输出的连接
- **THEN** 输出路径不包含原先由 `Smooth` 和 `Smooth Weight` 控制的整体 `expand_smooth()` 后处理

### Requirement: Smooth Weight 按独立消费者保留
系统 MUST 在 `Smooth Weight` 仍控制 `Boundary Smooth` 时保留该输入，并在它仅服务已删除的整体 smooth 时删除该输入。

#### Scenario: 深度节点组保留共享权重
- **WHEN** 检查 `O Image Depth Cutout`、`O Image Depth Plane` 或 `O Image Depth Panorama`
- **THEN** 节点组仍提供 `Smooth Weight`，且该值继续参与边界平滑计算

#### Scenario: 无独立消费者的权重被删除
- **WHEN** 检查 `O Image Cutout` 或 `O Image Relief Plane`
- **THEN** 节点组接口不包含 `Smooth Weight`

### Requirement: 专用平滑行为保持可用
系统 SHALL 保留与末端整体 mesh smooth 不同职责的边界平滑、法线平滑、填充墙体平滑和 smooth shading。

#### Scenario: 深度边界和法线控制仍存在
- **WHEN** 检查受影响深度节点组的接口与计算路径
- **THEN** 既有 `Boundary Smooth` 与适用的 `Normal Smooth` 仍按原职责工作

#### Scenario: 填充与着色平滑不受影响
- **WHEN** 构建相关节点组并检查输出
- **THEN** `Fill Smooth` 仍仅用于生成墙体内部，且既有 smooth shading 仍应用于对应表面
