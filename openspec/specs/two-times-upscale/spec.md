# two-times-upscale Specification

## Purpose
TBD - created by archiving change add-pisa-sr-two-times-upscale. Update Purpose after archive.
## Requirements
### Requirement: Unified two-times output

系统 SHALL 对全部 Upscale 模型返回处理输入宽高各 2 倍的结果，并将该倍率用于界面说明和尺寸计算；处理输入为应用已有最大输入尺寸限制后的图像。

#### Scenario: Existing models produce two-times images
- **WHEN** 任一现有模型处理 W×H 输入
- **THEN** 系统先得到原生 4W×4H 结果，再使用 Lanczos 缩小到 2W×2H
- **AND** 使用已有 4× 权重

#### Scenario: Repeated upscale
- **WHEN** 用户对一次 2× 结果再次执行 Upscale 且输入尺寸仍满足限制
- **THEN** 新结果宽高各为本次输入的 2 倍，即最初输入的 4 倍

### Requirement: Fixed PiSA-SR preset

系统 SHALL 提供 `PISA_SR` 模型选项，使用固定像素强度 1.0、语义强度 0.7、空提示词和 seed 42，通过 ONNX Runtime 生成 2× 结果。现有默认模型 SHALL 保持有效。

#### Scenario: Selected preset is executed
- **WHEN** 用户选择 PiSA-SR 并执行 Upscale
- **THEN** 模型对同一 latent 的预测按 `pixel + 0.7 * (full - pixel)` 组合
- **AND** 输入插值、采样、解码与颜色校正遵循已验证的实验基线

#### Scenario: Repeatable inference
- **WHEN** 相同图像在相同运行环境重复执行 PiSA-SR
- **THEN** 系统使用相同噪声和处理规则，结果在该设备的数值容差内一致

### Requirement: Arbitrary dimensions and alpha preservation

系统 SHALL 支持合法输入范围内的小图、非方形图、奇数尺寸和跨 tile 图像，输出精确 2× 尺寸；有 alpha 的生产输入 SHALL 保留由源 alpha 插值而来的透明度。

#### Scenario: Tiled PiSA-SR image
- **WHEN** 输入需要多个 PiSA-SR tile
- **THEN** 系统融合重叠区域并裁去填充，输出无多余边缘的 2W×2H 图像
- **AND** 连续纹理与渐变测试图的 tile 边界不出现可辨识拼接线

#### Scenario: Transparent input
- **WHEN** 输入包含全透明和半透明像素
- **THEN** 输出 alpha 等于源 alpha 直接 Lanczos 放大到最终尺寸的结果
- **AND** RGB 生成过程不生成或覆盖 alpha

### Requirement: Model readiness and resource lifecycle

系统 SHALL 对 PiSA-SR 全部必需资产完成下载及校验后才判定就绪，按所选设备创建管线；其模型切换、取消、资源错误和显式清理 SHALL 覆盖全部组件。

#### Scenario: Incomplete model package
- **WHEN** PiSA-SR 任一必需文件缺失或校验失败
- **THEN** 系统提示准备模型并阻止使用不完整管线进行推理

#### Scenario: Bounded UNet residency
- **WHEN** PiSA-SR 执行像素与完整预测阶段
- **THEN** GPU 同时常驻的 UNet 至多一套，阶段间中间数据被保留以完成 0.7 组合

#### Scenario: Cancel or resource failure
- **WHEN** 推理被取消或发生资源错误
- **THEN** 系统停止后续阶段并清理任务中间文件
- **AND** 资源错误释放整个 PiSA-SR 管线并报告可理解的失败原因

#### Scenario: Unsupported device
- **WHEN** 所选设备无法执行已分发的 PiSA-SR 资产
- **THEN** 系统报告明确的设备支持原因或执行已验证并明确呈现的回退路径

### Requirement: Consistent job behavior

系统 SHALL 在生产与调试任务采用同一模型预设和最终倍率，并对多帧输入逐帧应用该约定。

#### Scenario: Multiple frames
- **WHEN** Upscale 处理多帧输入
- **THEN** 每帧输出均为其处理输入的 2× 尺寸，帧顺序正确且阶段之间可以取消

#### Scenario: Debug matches production
- **WHEN** 相同 RGB 输入、模型和设备分别通过生产与 Debug 入口处理
- **THEN** 两者的 RGB 处理规则和最终尺寸一致

