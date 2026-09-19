## ADDED Requirements

### Requirement: One conversion exposes two geometry modes

系统 SHALL 仅提供 Convert to Depth Plane 整图深度入口，使用 `anyimage.convert_to_depth_plane` 与资产组 `O Image Depth Plane`。Mode SHALL 提供 Relief 与 Camera，默认 Relief。独立 Depth Surface 入口、注册类和公开资产组 SHALL 删除。

#### Scenario: Convert and switch modes
- **WHEN** 静态 Image Empty 完成转换后，用户在修改器切换 Relief / Camera
- **THEN** 同一对象和深度图片产生对应几何，不重新推理、不创建新深度图片
- **AND** 两种模式共享并保留已有控制值

#### Scenario: Preserve conversion lifecycle
- **WHEN** 转换成功或失败
- **THEN** 成功时沿用源名称、替换源对象且一次 Undo 可恢复；失败时清理部分结果并保留源对象
- **AND** AI 环境检查和静态媒体限制继续生效

### Requirement: Unified modifier has a stable interface

接口 SHALL 依次为 Geometry、Mode、Subdivide、两个独立的 Thickness、Depth Scale、Options 内 Reference Depth 与 Normal Smooth、Data 内 Uniform Scale 与 Depth Image。两个 Thickness SHALL 同名显示，依次控制 Relief 与 Camera，默认均为 0 m、最小 0，使用不同 identifier 独立保存。Subdivide SHALL 默认为 6、范围 0–10；Depth Scale 默认为 1、最小 0；Normal Smooth 默认为 50、范围 0–50。Reference Depth SHALL 由元数据基准深度乘以 Uniform Scale 初始化。Data 输入 SHALL 隐藏；所有输入 SHALL 使用 SINGLE，长度使用 DISTANCE。

#### Scenario: Inspect mode controls
- **WHEN** 创建或切换修改器模式
- **THEN** 接口顺序和默认值符合契约，Normal Smooth 只影响 Camera 的厚度法线
- **AND** 整图模式不提供 Split 或 Cutout 轮廓控制

#### Scenario: Keep mode thickness independent
- **WHEN** 在一种模式中修改另一模式对应的 Thickness，并切换模式后返回
- **THEN** 当前模式几何保持不变，两个厚度值分别保留

### Requirement: Relief preserves the fixed base

Relief SHALL 读取 B/Z 深度，保持基础 XY、固定底面、现有侧壁插值和负位移限制。Thickness SHALL 表示浮雕的基础厚度。

#### Scenario: Evaluate relief
- **WHEN** 用与旧标量输入相同的 Z、不同的 X/Y 求值 Relief
- **THEN** 顶点位置、面连接、UV 与材质和原 Depth Plane 结果一致

### Requirement: Camera preserves the projected shell

Camera SHALL 使用完整矩形细分；相机 XYZ 乘以 Uniform Scale 后得到 C，XY SHALL 按 Depth Scale 从基础 XY 插值到 `(C.x, -C.y)`，Z SHALL 为 `(Reference Depth - C.z) × Depth Scale`。零 Thickness SHALL 输出单层；正 Thickness SHALL 沿平滑归一化后的正面 POINT 法线向内生成背面并闭合边界。

#### Scenario: Match the ordinary plane
- **WHEN** Camera 的 Thickness 和 Depth Scale 均为 0
- **THEN** 相同 Subdivide 下几何与普通 Plane 一致，包括非中心显示偏移和对象变换后的世界位置

#### Scenario: Project and thicken
- **WHEN** 使用非中心主点合成数据，Depth Scale 为 0、0.5、1 或 2，Normal Smooth 为 0、2 或 50
- **THEN** 投影符合公式；正 Thickness 的对应正背面距离等于 Thickness，0 次平滑使用原始法线
- **AND** 透明区域与深度跳变区域保持完整矩形连接

### Requirement: Asset evaluation preserves geometry data

统一组 SHALL 从资产按名称加载，保留 UV、材质和用户属性，并清理自身临时属性。定义和保存资产 SHALL 满足相同接口与几何契约，布局 SHALL 在 Blender 中按实际绘制尺寸检查。

#### Scenario: Validate the delivered asset
- **WHEN** 加载更新后的节点资产
- **THEN** 公开组清单包含统一 Depth Plane 且没有独立 Depth Surface，两种模式通过几何求值
- **AND** 总览和局部步骤没有节点遮挡，未用输出隐藏，主轴与支线清楚
