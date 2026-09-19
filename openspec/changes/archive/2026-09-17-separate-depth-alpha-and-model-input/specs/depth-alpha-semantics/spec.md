## Purpose

规定透明图进入 MoGe2 时的颜色语义、轮廓深度延伸范围和深度产物的有效性通道，使 Depth Plane 根据图像覆盖与模型判断剔除几何，同时为 Cutout 提供稳定的轮廓深度采样。

## ADDED Requirements

### Requirement: Model input preserves source RGB

系统 SHALL 使用输入图 RGB 准备 MoGe2 输入，缩放 SHALL 基于 RGB 执行，alpha MUST 保持为独立信号。

#### Scenario: Same RGB with different alpha
- **WHEN** 两张尺寸、RGB 相同的图仅 alpha 不同，并使用相同输入尺寸上限
- **THEN** 它们生成的模型 RGB 输入相同，包括触发缩放的情况

#### Scenario: Transparent sky retains color context
- **WHEN** Remove BG 输出保留天空 RGB 并将其 alpha 设为零
- **THEN** MoGe2 输入保留天空 RGB，输出深度产物对应像素的 Alpha 为零

### Requirement: Alpha silhouette determines depth extension

系统 SHALL 根据原图 alpha 确定可见分量和轮廓修补范围，使用同一分量的可靠深度延伸轮廓。模型有效性 MUST 用于排除不可靠来源，修补范围 SHALL 独立于模型 mask 孔洞。延伸 SHALL 保持原始 alpha、模型有效性与未修补区域的深度。

#### Scenario: Repair the alpha edge
- **WHEN** alpha 轮廓内侧保护带及轮廓外采样带存在不稳定深度，且分量内部存在可靠来源
- **THEN** 系统使用该分量可靠深度修补边界，并保持目标像素的相机投影射线

#### Scenario: Internal mask hole
- **WHEN** 一个低 mask 区域完全位于 alpha 轮廓保护带以外的内部
- **THEN** 该区域不会仅因 mask 偏低而成为延伸目标，其模型有效性保持原值

#### Scenario: Fully opaque input
- **WHEN** 输入 alpha 全为 1
- **THEN** 系统保留原始深度场，包括低 mask 区域

#### Scenario: Component lacks reliable depth
- **WHEN** 某个 alpha 分量没有可靠深度来源
- **THEN** 该分量保留原始深度，不从其他分量借用深度

### Requirement: Depth artifact alpha combines coverage and model validity

`depth.exr` SHALL 在 RGB 保存相机空间 XYZ，在 Alpha 保存对齐预测尺寸的原图 alpha 与原始模型有效性的逐像素乘积。两个信号 MUST 保留连续值，补边 MUST 保持乘积所用的原始信号。

#### Scenario: Continuous values
- **WHEN** 某像素原图 alpha 为 0.8，模型有效性为 0.75
- **THEN** 导出的 Alpha 为 0.6，XYZ 保留该像素的深度处理结果

#### Scenario: Invisible or model-invalid pixel
- **WHEN** 原图 alpha 或模型有效性任一为零
- **THEN** EXR Alpha 为零，XYZ 仍保存可供采样的数值场

### Requirement: Geometry consumers use depth channels by purpose

Depth Plane SHALL 通过现有 Valid Only 和 Validity Threshold 按 EXR Alpha 剔除。Cutout SHALL 根据自身轮廓生成曲面并读取 XYZ，EXR Alpha 不得引入额外曲面剔除。

#### Scenario: Depth plane culling
- **WHEN** Valid Only 开启且原图 alpha 或模型有效性使乘积低于当前阈值
- **THEN** 该采样位置按现有节点的面域规则参与剔除

#### Scenario: Culling disabled
- **WHEN** 用户关闭 Valid Only
- **THEN** 完整细分网格继续进入深度投影与厚度处理

#### Scenario: Cutout keeps its contour
- **WHEN** Cutout 轮廓内含低 EXR Alpha 区域
- **THEN** 曲面拓扑保持由 Cutout 轮廓决定，深度采样使用导出的 XYZ
