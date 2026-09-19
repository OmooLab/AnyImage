# image-edit-tools Specification

## Purpose
TBD - created by archiving change replace-crop-with-mask-and-rectify. Update Purpose after archive.
## Requirements
### Requirement: Image Edit group uses Frame Mask and Rectify
系统 SHALL 将图片编辑工具组依次注册为 **Frame**、**Mask** 和 **Rectify**，并 SHALL 将 Cutout 作为其后的独立工具。系统 MUST NOT 注册旧 Crop Lasso、Crop Polyline 或 Crop Perspective Tool ID，也 MUST NOT 提供旧 ID 的兼容入口。

#### Scenario: Image Edit tools are registered
- **WHEN** AnyImage 扩展完成注册
- **THEN** 3D Viewport 图片编辑工具组按 Frame、Mask、Rectify 顺序显示，Cutout 紧随其后

#### Scenario: Legacy Crop tools are absent
- **WHEN** 系统枚举已注册的 AnyImage WorkspaceTool 和 Operator
- **THEN** 不存在 Crop Lasso、Crop Polyline、Crop Perspective 或其旧 ID

### Requirement: Mask combines Lasso and Brush gestures
Mask SHALL 是一个 WorkSpaceTool 和一个图片 Alpha 编辑 Operator，并 SHALL 提供 `LASSO` 与 `BRUSH` Gesture。两种 Gesture MUST 生成相同的 SelectionMask 产物并进入相同的 Alpha 合成入口。

#### Scenario: Lasso edits Alpha
- **WHEN** 用户在 Mask 中选择 Lasso 并完成一个有效闭合手势
- **THEN** 系统将该 Lasso 栅格化一次并按当前 Mode 编辑 active Image Empty 的 Alpha

#### Scenario: Brush edits Alpha
- **WHEN** 用户在 Mask 中选择 Brush 并完成一次点击或拖动
- **THEN** 系统将连续圆形笔画栅格化一次并按当前 Mode 编辑 active Image Empty 的 Alpha

### Requirement: Mask provides three Alpha modes
Mask SHALL 提供 `SET`、`ADD`、`SUBTRACT` 三种互斥 Mode，并 SHALL 在 Tool Settings 中使用 Set、Add、Subtract 图标展开显示。设当前 Alpha 为 `A`、本次 SelectionMask 权重为 `M`，系统 MUST 分别计算 `A × M`、`max(A, M)`、`A × (1 - M)`，同时保持 RGB 不变。

#### Scenario: Set keeps only current content inside the gesture
- **WHEN** 用户以 Set 应用一次 Mask 手势
- **THEN** 手势外 Alpha 变为零，手势内 Alpha 等于当前 Alpha 与 SelectionMask 权重的乘积

#### Scenario: Add extends current Alpha
- **WHEN** 用户以 Add 应用一次 Mask 手势
- **THEN** 每个像素 Alpha 等于当前 Alpha 与 SelectionMask 权重的较大值

#### Scenario: Subtract removes current Alpha
- **WHEN** 用户以 Subtract 应用一次 Mask 手势
- **THEN** 每个像素 Alpha 等于当前 Alpha 与 SelectionMask 补集的乘积

#### Scenario: Fractional edge coverage is preserved
- **WHEN** SelectionMask 边缘包含 `0` 与 `1` 之间的权重
- **THEN** 系统使用该权重执行对应公式而不是先转为布尔值

### Requirement: Mask settings persist per scene
系统 SHALL 在 Scene 中保存 Mask 的 Gesture、Mode 和 Radius。Radius SHALL 是正整数 Region 屏幕像素，默认 25 px，并 MUST 仅在 Gesture 为 Brush 时显示和生效；每次手势开始后 MUST 冻结本次使用的设置。

#### Scenario: Mask settings are reused
- **WHEN** 用户设置 Brush、Add 和一个 Radius 后完成一次操作并再次使用 Mask
- **THEN** Tool Settings 保持 Brush、Add 和该 Radius

#### Scenario: Lasso hides Radius
- **WHEN** Mask Gesture 为 Lasso
- **THEN** Tool Settings 不显示 Radius 且 Lasso 栅格化不读取 Radius

### Requirement: Brush produces continuous screen-space coverage
Brush SHALL 以当前 Region 中的屏幕像素显示 Radius 圆环，并 MUST 让单击产生圆形覆盖、拖动产生带圆角端点的连续覆盖。快速移动时相邻事件点之间 MUST NOT 留下未覆盖间隙，图片范围外的笔画 MUST 被裁到图片画布。

#### Scenario: Single click stamps a circle
- **WHEN** 用户以 Brush 在图片上单击而不拖动
- **THEN** 系统以点击位置和当前 Radius 生成一个圆形 SelectionMask

#### Scenario: Sparse motion events remain connected
- **WHEN** 一次 Brush 拖动的相邻采样点距离大于 Radius
- **THEN** 两点之间仍由连续笔画覆盖

#### Scenario: Viewport scale does not change displayed Radius
- **WHEN** 用户改变 Viewport 缩放后以同一 Radius 使用 Brush
- **THEN** 笔刷圆环在 Region 中继续使用相同屏幕像素半径

### Requirement: Mask preserves the rectangular image canvas
Mask SHALL 创建与当前图片相同宽高的 packed Image，并 SHALL 保持 active Image Empty 的对象身份、matrix、display size 和 image offset。Mask MUST NOT 按 Alpha 紧裁切或传入 placement bounds，且 SHALL 允许产生全透明结果。

#### Scenario: Lasso keeps the canvas
- **WHEN** Lasso 手势只覆盖图片的一小部分
- **THEN** 结果图片尺寸和 Image Empty 矩形画框与操作前完全相同

#### Scenario: Brush keeps the canvas
- **WHEN** Brush 手势只覆盖图片的一小部分
- **THEN** 结果图片尺寸和 Image Empty 矩形画框与操作前完全相同

#### Scenario: Entire Alpha can be removed
- **WHEN** Subtract 覆盖当前全部非零 Alpha
- **THEN** 操作成功并产生相同尺寸的全透明结果

#### Scenario: Shared source remains unchanged
- **WHEN** active Image Empty 与其他对象共享同一个源 Image
- **THEN** active 对象改为引用新的编辑结果，其他对象继续引用未修改的源 Image

### Requirement: Mask and Rectify replace the active image
Mask 与 Rectify SHALL 直接替换 active Image Empty 承载的 Image，并 MUST NOT 提供 Keep Original 属性、Operator 参数或复制结果对象的路径。Frame SHALL 继续让 active Image Empty 承载合成结果。

#### Scenario: Mask replaces the active result
- **WHEN** 用户完成一次 Mask 操作
- **THEN** active Image Empty 本身承载结果且系统不创建其副本

#### Scenario: Rectify replaces the active result
- **WHEN** 用户完成一次 Rectify 操作
- **THEN** active Image Empty 本身承载结果且系统不创建其副本

### Requirement: Rectify performs four-point perspective correction
Rectify SHALL 接受四个图片点，规范化为有效凸 Quad，并通过 Homography 生成目标宽高比的矩形图片。系统 SHALL 保留现有预览、输出分辨率限制、可见 Alpha trim 和结果 placement 语义，同时 SHALL 在类名、Tool/Operator ID、标签、状态、warning 与 Undo 中统一使用 Rectify 术语。

#### Scenario: Four points create a rectified image
- **WHEN** 用户为 still Image Empty 提交四个构成有效凸 Quad 的点
- **THEN** 系统生成透视校正后的矩形图片并替换 active Image Empty 的 Image

#### Scenario: Rectify retains output limits
- **WHEN** 四点区域对应的原始输出超过长边或总像素限制
- **THEN** 系统按既有 Rectify 输出限制等比约束结果

### Requirement: Refine Selection is absent from Mask and Cutout
Mask 与 Cutout MUST NOT 声明、显示、保存或传递 Refine Selection。Server MUST NOT 注册 `refine-image-selection` Job，Cutout Job MUST NOT 接收或执行 `refine_selection` 与 `refine_model`；BEN2 Remove Background 与 Debug 能力 SHALL 保持可用。

#### Scenario: Mask has no AI refinement
- **WHEN** 用户查看 Mask Tool Settings 或执行 Mask
- **THEN** 不存在 Refine Selection 选项、AI readiness 门控或 BEN2 Job

#### Scenario: Cutout runs without refinement parameters
- **WHEN** 用户创建本地、Depth 或 Normal Cutout
- **THEN** Blender 和 Server 请求中不包含 Refine Selection 参数，最终 Shape 仍由本地几何 SelectionMask 约束

#### Scenario: BEN2 remains available elsewhere
- **WHEN** 用户运行 Remove Background 或 BEN2 Debug
- **THEN** 系统继续使用现有 BEN2 模型与缓存完成请求

