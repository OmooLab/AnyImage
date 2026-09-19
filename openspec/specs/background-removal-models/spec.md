# background-removal-models Specification

## Purpose
TBD - created by archiving change simplify-ai-model-tiers. Update Purpose after archive.
## Requirements
### Requirement: 背景模型选择贯穿真实执行
系统 SHALL 使用当前选择的 BiRefNet Lite、BEN2 或 BiRefNet HR-matting 执行所有支持的背景移除输入路径，模型名称 SHALL 与下载、进度和实际加载的资源一致。

#### Scenario: 切换到精细抠图
- **WHEN** 用户选择已经下载的 BiRefNet HR-matting 并执行背景移除
- **THEN** 使用该模型推理，输出和进度不再固定指向 BEN2

### Requirement: 输出有限的连续透明度
每款背景模型 SHALL 产出与分析图片尺寸一致、有限且位于 `[0,1]` 的连续 Alpha。模型适配 SHALL 保持其官方输出语义，支持发丝、毛绒和半透明边缘的连续透明度。

#### Scenario: 半透明边缘
- **WHEN** HR-matting 对包含薄纱或细发丝的图片输出中间透明度
- **THEN** 后处理保留有效的中间 Alpha 值，不将其强制二值化或按单图极值重新拉伸

#### Scenario: 无效预测
- **WHEN** 模型返回错误形状或包含 NaN、Inf 的透明度
- **THEN** 任务明确失败，并保留可诊断的模型错误信息

### Requirement: 保持已有前景和 HDR 编辑行为
系统 SHALL 沿用既有前景 RGB 与源 Alpha 合成规则，支持静态前景、多帧前景及 HDR 的 Alpha-only 输出；HDR 结果 SHALL 保持原始浮点 RGB。

#### Scenario: HDR 背景移除
- **WHEN** 用户对浮点 HDR 图片使用任意背景模型
- **THEN** 用分析输入预测 Alpha，将结果应用到原始图片，并保留原始 HDR RGB 数值

#### Scenario: 多帧透明前景
- **WHEN** 用户对支持的多帧输入执行背景移除
- **THEN** 每帧使用选定模型，保持帧数、编号、尺寸与已有透明度合成约定

### Requirement: 模型资源可复用且可释放
系统 SHALL 为相同模型和设备复用会话，在模型切换、资源关闭时释放旧会话，并使取消与失败遵循既有任务清理行为。

#### Scenario: 连续帧复用
- **WHEN** 多帧任务连续处理同一模型和设备
- **THEN** 各帧复用已加载会话，取消后停止后续推理并清理未完成任务产物

#### Scenario: 切换背景模型
- **WHEN** 用户从 Lite 切换到 BEN2 或 HR-matting
- **THEN** 实际推理使用新选择，并释放原先背景模型占用的会话资源

### Requirement: 新背景模型经过真实运行验收
BiRefNet Lite SHALL 在发布前通过 CPU / DirectML 数值和图片验证，HR-matting SHALL 通过 CPU 验证；记录真实下载体积、加载与热推理耗时、峰值资源占用及边缘效果。Lite SHALL 比 BEN2 下载体积更小，并在相同测试条件下至少降低热推理耗时或峰值占用中的一项。

#### Scenario: 确定轻量默认模型
- **WHEN** Lite 的正式资产准备发布
- **THEN** 存在与 BEN2 的同条件对照和质量检查记录，且其轻量收益满足要求

### Requirement: HR-matting 使用 CPU
HR-matting SHALL 暂时固定使用 CPU。模型选项 SHALL 标明 CPU，进度 SHALL 显示实际设备；会话缓存 SHALL 按实际 CPU 设备复用。

#### Scenario: GPU 偏好下选择 HR-matting
- **WHEN** 全局设备为 DirectML，用户选择 HR-matting
- **THEN** 创建 CPU 会话并显示 CPU 进度，保持 HR 的 2048 像素输入及连续 Alpha 语义

