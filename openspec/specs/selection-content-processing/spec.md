# selection-content-processing Specification

## Purpose
TBD - created by archiving change refine-image-output-semantics. Update Purpose after archive.
## Requirements
### Requirement: Refine preserves the submitted bounds canvas
系统 SHALL 让 BEN2 Refine 输出保持输入 RGBA 的完整矩形尺寸，并沿用提交前的 Selection bounds；Server MUST 不按生成 Alpha 紧裁切输出，也 MUST 不接收 Selection Mask。

#### Scenario: BEN2 output occupies only part of the bounds
- **WHEN** BEN2 只在输入矩形的一部分生成可见 Alpha
- **THEN** Refine 输出 SHALL 保留完整输入尺寸和透明区域，Blender SHALL 沿用提交前保存的 bounds

#### Scenario: Refine Job reports its files
- **WHEN** `refine-image-selection` 或 Cutout artifact Job 完成 Refine
- **THEN** Job SHALL 返回完整尺寸的 Refine 图片，并且 MUST 不生成或返回 Refine 后的局部 bounds 文件

### Requirement: Refined content Alpha combines source and BEN2
BEN2 Refine 内容 Alpha SHALL 等于 `Source Alpha × BEN2 Alpha`，并且 Selection Mask MUST 不参与 BEN2 推理或 Server 端 Refine 输出。

#### Scenario: Source contains transparent pixels
- **WHEN** BEN2 在源 Alpha 为零或半透明的像素生成前景 Alpha
- **THEN** Refine 图片 SHALL 通过 `preserve_input_alpha` 保持源 Alpha 与 BEN2 Alpha 的乘积

#### Scenario: Selection excludes visible content inside bounds
- **WHEN** bounds 内存在位于 Selection Mask 外的可见内容
- **THEN** BEN2 与 Server Refine 输出 SHALL 仍能使用并保留该内容，不得预先乘入 Selection Mask

### Requirement: Cutout textures share refined content scope
启用 Refine Selection 的 Cutout SHALL 使用同一份 `Source Alpha × BEN2 Alpha` 内容生成 Color、Normal 与 Depth 贴图，Selection Mask MUST 不限制这些贴图的生成。

#### Scenario: Cutout generates color and normal
- **WHEN** Cutout 同时启用 Refine Selection 与 Normal Map
- **THEN** Color Alpha 与 Normal 可见区域 SHALL 来自完整 Refine 图片 Alpha，不得乘入 Selection Mask

#### Scenario: Cutout generates depth
- **WHEN** Refined Cutout 生成 Vector 或 Z Depth
- **THEN** MoGe-2 黑底输入和 Depth Metadata 参考内容范围 SHALL 来自完整 Refine 图片 Alpha，不得乘入 Selection Mask

#### Scenario: Depth texture preserves model validity
- **WHEN** 系统写出 Vector 或 Z Depth EXR
- **THEN** RGB SHALL 保留完整连续 Field，Alpha SHALL 保存 MoGe-2 Validity，不得用 Refine Alpha 或 Selection Mask 覆盖

### Requirement: Cutout mesh combines refined content with Selection
Cutout SHALL 只在 Blender 网格构建阶段计算 `Source Alpha × BEN2 Alpha × Selection Mask`，并使用该结果约束 BaseShape、内容空值检查和网格标定。

#### Scenario: BEN2 keeps content outside the user Selection
- **WHEN** BEN2 在 Selection bounds 内保留了 Selection Mask 外的前景
- **THEN** Color、Normal 与 Depth SHALL 保留该内容，但最终 Cutout 网格 MUST 不包含 Selection Mask 外的区域

#### Scenario: Combined Cutout content is empty
- **WHEN** Refine Alpha 与 Selection Mask 相乘后没有超过 Cutout Alpha 阈值的像素
- **THEN** Cutout SHALL 报告空内容且不创建网格

#### Scenario: Cutout generates only Normal or Depth
- **WHEN** Cutout 未启用 Refine、但因 Normal 或 Depth 进入 Job
- **THEN** 贴图 SHALL 使用完整 bounds 源 Alpha，网格 SHALL 使用 `Source Alpha × Selection Mask`

### Requirement: Crop Refine applies Selection in Blender
Crop Refine SHALL 在 Blender 中计算 `Source Alpha × BEN2 Alpha × Selection Mask` 作为最终图片 Alpha，同时保持提交前的矩形尺寸和 placement bounds。

#### Scenario: BEN2 keeps pixels outside a Crop Selection
- **WHEN** BEN2 在 Crop Selection Mask 外生成可见 Alpha
- **THEN** 最终 Crop 图片 SHALL 将这些像素 Alpha 置为零，但 MUST 不改变提交前 bounds

#### Scenario: Crop uses one rasterized Selection
- **WHEN** Crop 提交 Refine Job 并异步接收结果
- **THEN** 系统 SHALL 复用提交阶段生成的 Selection Mask，不得在响应阶段重新栅格化 SelectionPath，也不得把 Mask 发送给 Server

#### Scenario: Combined Crop content is empty
- **WHEN** Refine Alpha 与 Selection Mask 相乘后没有可见像素
- **THEN** Crop SHALL 报告空内容且不创建结果 Image Empty

### Requirement: Selection Mask is independent of image content
系统 SHALL 仅根据 Selection Path、Invert、图片尺寸与抗锯齿设置栅格化 Selection Mask，并且 Selection 栅格化不得读取、接收或合并源图片 Alpha、颜色或 Alpha threshold。

#### Scenario: Images have different Alpha
- **WHEN** 相同 Selection Path、图片尺寸与抗锯齿设置用于透明度内容不同的图片
- **THEN** 系统产生逐值相同且 bounds 相同的 Selection Mask

#### Scenario: Selection is inverted
- **WHEN** Selection Path 启用 Invert
- **THEN** 系统在完整图片画布上产生路径外的纯几何 Selection Mask，而不检查源图片可见内容

### Requirement: Image businesses combine source Alpha explicitly
系统 SHALL 由 Image Tool 与本地 Cutout 在实际业务阶段显式组合 Selection Mask 值和对应 Bounds 内的源 Alpha；Selection Mask MUST 在组合前后保持纯几何值不变。

#### Scenario: Image Tool edits a Selection
- **WHEN** 用户提交未启用 Refine 的 Image Tool Selection
- **THEN** Image Tool 在几何 bounds 内把 Selection 值乘入源 Alpha，并由编辑业务计算内容 bounds、空结果和最终图片

#### Scenario: Local Cutout builds a Shape
- **WHEN** 用户选择不需要 AI 的 Cutout Shape
- **THEN** Cutout 在构建 Shape 时组合局部源 Alpha 与 Selection 值，并使用业务结果约束几何和判断空内容

#### Scenario: Source content is transparent
- **WHEN** 几何 Selection 有效但对应源 Alpha 没有可见内容
- **THEN** 消费该内容的 Image 或 Cutout 业务报告空内容，Selection 栅格化本身仍成功

### Requirement: AI receives one rectangular Bounds image
系统 SHALL 为需要 AI 的 Image Tool 或 Cutout 按 Selection 几何 bounds 写出一份矩形局部 RGBA 文件，并且该文件 MUST 保留 bounds 内的源 Alpha，不得预先乘入 Lasso Selection 值。

#### Scenario: Refine receives Lasso context
- **WHEN** 用户对 Lasso Selection 启用 Refine
- **THEN** BEN2 接收 Lasso 几何 bounds 对应的完整矩形 RGBA，矩形内、Lasso 外的源像素保持原样

#### Scenario: Normal or Depth requires AI
- **WHEN** Cutout 仅因 Normal 或 Depth 进入 AI 流程
- **THEN** Job 使用与 Refine 相同的 Bounds 矩形输入协议，不建立另一套 Masked Selection 输入

#### Scenario: Blender Image source varies
- **WHEN** 源 Image 来自文件、Packed 数据或 Blender 内存
- **THEN** Operator 通过同一个 Bounds 图片序列化入口产生 AI 输入，不按来源建立不同业务主链

### Requirement: Refine may expand within Selection Bounds
系统 SHALL 将 Refine 的 Lasso 解释为矩形上下文范围，而不是 BEN2 输出的硬 Mask；最终 Refine Alpha SHALL 由 BEN2 在该矩形内的结果决定。

#### Scenario: BEN2 preserves content outside Lasso
- **WHEN** BEN2 在 Selection bounds 内保留了 Lasso 路径外的像素
- **THEN** 系统保留这些像素，不再与原始 Lasso Selection Mask 相交

#### Scenario: BEN2 returns no visible content
- **WHEN** Refine 输出在矩形 bounds 内没有可见 Alpha
- **THEN** Refine 业务报告空内容且不创建 Image 或 Cutout 结果

### Requirement: AI operations reuse encoded local images
系统 SHALL 复用 AI 流程中已经编码的局部 RGBA 文件作为最终颜色 Image，不得重新读取完整源图并创建包含相同颜色内容的新内存 Image 后再次编码。

#### Scenario: Image Tool Refine completes
- **WHEN** BEN2 返回已收紧 bounds 的 Refine RGBA 文件
- **THEN** Image Tool 直接加载、配置并 Pack 该文件，然后按响应 bounds 替换源 Image Empty

#### Scenario: Cutout Refine completes
- **WHEN** Cutout 的 BEN2 Refine 返回局部 RGBA 文件
- **THEN** Cutout 使用该文件的 Alpha 构建结果几何，并使用同一个已加载 Image 作为颜色纹理

#### Scenario: Cutout generates only Normal or Depth
- **WHEN** Cutout AI 流程没有 Refine 输出
- **THEN** Cutout 直接加载并 Pack 提交前的 Bounds 输入作为颜色纹理

#### Scenario: AI operation cleans up
- **WHEN** 已有输入或 Refine 输出成功加载并 Pack，或者操作取消
- **THEN** 系统按 Job 生命周期清理临时文件，且 Blender 结果不再依赖临时路径

