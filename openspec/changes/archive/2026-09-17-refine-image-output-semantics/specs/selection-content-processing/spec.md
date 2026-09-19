## ADDED Requirements

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
