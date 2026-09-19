# hat-upscale Specification

## Purpose
TBD - created by archiving change simplify-ai-model-tiers. Update Purpose after archive.
## Requirements
### Requirement: HAT Sharper 提供可验证的小体积资源
系统 SHALL 提供官方 Real HAT GAN x4 Sharper 对应的模型资产，完整记录上游来源、文件大小及校验信息。发布文件 SHALL 小于 60 MB，保持 FP32 输入输出，并通过 CPU / DirectML 与原始 FP32 参考的数值对照。

#### Scenario: 校验发布模型
- **WHEN** 对预先固定的样图执行正式导出资产
- **THEN** 输出全部有限，未裁剪的 `[0,1]` 标度输出误差满足 MAE ≤ 0.0005、P99 ≤ 0.005、最大误差 ≤ 0.02

#### Scenario: 实验精度路径失败
- **WHEN** 导出或运行路径在验收中产生 NaN、Inf 或超过预设误差
- **THEN** 该资产不能登记为可发布模型，也不能标记验收完成

### Requirement: 三款超分均保持最终两倍输出
系统 SHALL 对限制后的分析输入保持宽高各 2 倍的最终输出；HAT 与现有两款 Real-ESRGAN SHALL 保持相同的透明度合成和帧输出约定。

#### Scenario: 普通与透明静态图片
- **WHEN** 用户用 HAT Sharper 放大宽 W、高 H 的分析输入
- **THEN** 最终图片尺寸为 `2W×2H`，原始 Alpha 按现有超分规则缩放并合成

#### Scenario: 多帧输入
- **WHEN** 使用 HAT Sharper 处理支持的多帧输入
- **THEN** 每帧输出保持两倍尺寸及既有编号，帧间复用模型资源

### Requirement: 分块支持合法图片尺寸且控制边界误差
HAT SHALL 支持小图、奇数尺寸和跨多个分块的输入，输出覆盖全部像素；分块配置 SHALL 通过纹理、细线和透明边缘样图检查，并相对完整参考记录接缝误差。

#### Scenario: 奇数尺寸与边缘块
- **WHEN** 输入宽高不是分块步长的整数倍
- **THEN** 结果保持准确的两倍尺寸，边缘完整，没有空白条带或重复像素区

#### Scenario: 自然纹理跨越接缝
- **WHEN** 对固定跨缝样图检查最终 2× 输出
- **THEN** 没有由拼接造成的可见直线接缝，并记录相对整图参考的接缝和内部误差

### Requirement: 推理取消和资源错误可处理
系统 SHALL 沿用超分任务的取消、会话复用和资源释放机制；资源不足时 SHALL 报告当前模型及可操作的调整建议。

#### Scenario: 分块间取消
- **WHEN** 用户取消正在处理多块图片的 HAT 任务
- **THEN** 后续块停止推理，未完成产物按现有任务规则清理

#### Scenario: 显存或内存不足
- **WHEN** 当前设备无法完成 HAT 推理
- **THEN** 返回包含模型和设备上下文的资源错误，提示减小分析输入或选择更轻量模型

