# moge-depth-artifacts Specification

## Purpose
TBD - created by archiving change normalize-moge-alpha-depth. Update Purpose after archive.
## Requirements
### Requirement: GeometryFrame 是统一几何预测边界

系统 SHALL 以单帧 `GeometryFrame` 表示供产物生成使用的几何预测。Frame SHALL 包含二维 float32 Depth、同尺寸 float32 Validity、3×3 float32 像素空间相机内参，以及可选的同尺寸三通道 float32 Normal 与 Points。Validity SHALL 统一保存模型提供的逐像素有效性信号。

#### Scenario: MoGe-2 预测适配
- **WHEN** MoGe-2 完成一帧预测
- **THEN** 系统生成包含 Depth、Normal、由原始 Mask 转换而来的 `0/1` Validity、像素空间相机内参与按需 Points 的 `GeometryFrame`

#### Scenario: DA3 预测适配
- **WHEN** DA3 预测被转换为统一几何结果
- **THEN** 系统生成包含 Depth、派生 Points、由原始 Confidence 提供的连续 Validity 与相机内参的 `GeometryFrame`，且 Normal 为空

#### Scenario: Frame 字段维度不一致
- **WHEN** 任一像素 Field 的高宽与 Depth 不一致，或相机内参不是 3×3
- **THEN** `GeometryFrame` 构建失败并报告字段维度错误

### Requirement: Geometry Artifact 只消费 GeometryFrame

系统 SHALL 从 `GeometryFrame` 生成 Vector Depth、Z Depth、Normal Map 与 Depth Metadata，Artifact Writer SHALL NOT 直接依赖 MoGe-2 或 DA3 专用 Prediction 类型。

#### Scenario: 生成 Vector Depth
- **WHEN** 一个 `GeometryFrame` 包含 Points
- **THEN** Vector Depth Writer 从 Frame 的 Points 与 Validity 生成 `vector-depth.exr`

#### Scenario: 生成 Z Depth 与 Metadata
- **WHEN** 一个 `GeometryFrame` 包含 Depth、Validity 与 Intrinsics
- **THEN** Z Depth 与 Metadata Writer 从该 Frame 生成 `z-depth.exr` 与 `depth.json`

#### Scenario: 生成 Normal Map
- **WHEN** 一个 `GeometryFrame` 包含 Normal
- **THEN** Normal Writer 从 Frame 的 Normal 及调用方提供的 Region 可见 Mask 生成 Normal Map

#### Scenario: 缺少所需 Field
- **WHEN** Writer 请求的 Points 或 Normal 在 `GeometryFrame` 中为空
- **THEN** 产物生成失败并报告缺少对应 Geometry Field

### Requirement: MoGe-2 使用统一黑底输入

系统 SHALL 在 MoGe-2 推理前将最终 Region RGBA 合成到黑底，模型 RGB SHALL 等于源 RGB 乘以归一化 Alpha。

#### Scenario: 完全透明像素
- **WHEN** 最终 Region 像素的 Alpha 为 `0`
- **THEN** MoGe-2 接收到的对应 RGB 为 `(0, 0, 0)`

#### Scenario: 半透明像素
- **WHEN** 最终 Region 像素的 Alpha 为 `0.5`
- **THEN** MoGe-2 接收到的对应 RGB 为源 RGB 的一半

#### Scenario: 完全不透明像素
- **WHEN** 最终 Region 像素的 Alpha 为 `1`
- **THEN** MoGe-2 接收到的对应 RGB 与源 RGB 相同

#### Scenario: 前景工作流输入一致
- **WHEN** Remove Background 与 Fit to Foreground 产生相同的可见 RGB 和 Alpha，仅完全透明像素下的隐藏 RGB 不同
- **THEN** 两条工作流提交给 MoGe-2 的模型 RGB 完全相同

### Requirement: Vector Depth 独立保存 Points 与 Validity

系统 SHALL 在 `vector-depth.exr` 的 RGB 中保存 `GeometryFrame.points` 的每个原始有限相机空间 XYZ，且 SHALL 不因 `GeometryFrame.validity` 为零而修改 XYZ；Alpha SHALL 只保存 `GeometryFrame.validity`。

#### Scenario: Validity 为零的有限 Point
- **WHEN** MoGe-2 为一个像素返回有限 XYZ 且原始 Mask 转换得到的 Validity 为 `0`
- **THEN** EXR RGB 等于该 XYZ，Alpha 等于 `0`

#### Scenario: Validity 为一的有限 Point
- **WHEN** MoGe-2 为一个像素返回有限 XYZ 且原始 Mask 转换得到的 Validity 为 `1`
- **THEN** EXR RGB 等于该 XYZ，Alpha 等于 `1`

#### Scenario: 输入 Alpha 不改变 Vector Depth Alpha
- **WHEN** Region 输入 Alpha 与 MoGe-2 原始 Mask 不同
- **THEN** `vector-depth.exr` Alpha 等于由 MoGe-2 原始 Mask 转换得到的 Validity

### Requirement: Z Depth 独立保存 Depth 与 Validity

系统 SHALL 在 `z-depth.exr` 的 RGB 三个通道中保存 `GeometryFrame.depth` 的每个原始有限 Depth，且 SHALL 不因 `GeometryFrame.validity` 为零而修改 Depth；Alpha SHALL 只保存 `GeometryFrame.validity`。

#### Scenario: Validity 为零的有限 Depth
- **WHEN** MoGe-2 为一个像素返回有限 Depth 且原始 Mask 转换得到的 Validity 为 `0`
- **THEN** EXR RGB 三个通道均等于该 Depth，Alpha 等于 `0`

#### Scenario: Validity 为一的有限 Depth
- **WHEN** MoGe-2 为一个像素返回有限 Depth 且原始 Mask 转换得到的 Validity 为 `1`
- **THEN** EXR RGB 三个通道均等于该 Depth，Alpha 等于 `1`

#### Scenario: 输入 Alpha 不改变 Z Depth Alpha
- **WHEN** Region 输入 Alpha 与 MoGe-2 原始 Mask 不同
- **THEN** `z-depth.exr` Alpha 等于由 MoGe-2 原始 Mask 转换得到的 Validity

### Requirement: Depth Artifact 拒绝非有限结果

系统 MUST 在写入 Depth EXR 前校验所有待写入 Depth 或 XYZ；任何通道包含 NaN 或 Inf 时 MUST 终止 Artifact 生成并报告错误，且 MUST NOT 以零值替换。

#### Scenario: Vector Depth 包含非有限值
- **WHEN** 任意原始 XYZ 分量为 NaN 或 Inf
- **THEN** `vector-depth.exr` 生成失败并报告无效 Point Field

#### Scenario: Z Depth 包含非有限值
- **WHEN** 任意原始 Depth 为 NaN 或 Inf
- **THEN** `z-depth.exr` 生成失败并报告无效 Depth Field

### Requirement: 校准筛选不改写 Depth Artifact

系统 SHALL 按需使用输入 Alpha、正的 `GeometryFrame.validity`、正 Depth 与有限性共同筛选 Depth Metadata 的参考样本，但 SHALL NOT 把该派生筛选结果存为 Frame 的第二套有效性字段，且 SHALL NOT 改写 Depth EXR 的 RGB 或 Alpha。

#### Scenario: 零 Validity 区域存在连续 Depth
- **WHEN** Validity 为零的区域存在有限 Depth 或 XYZ
- **THEN** 这些值保留在 EXR RGB 中，同时不进入参考深度计算

