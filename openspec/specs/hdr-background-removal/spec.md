# hdr-background-removal Specification

## Purpose
TBD - created by archiving change add-ben2-hdr-support. Update Purpose after archive.
## Requirements
### Requirement: HDR still image preparation

系统 SHALL 为可读的浮点静态图片提供 Remove Background，覆盖 Image Empty 与材质 Image Texture 的外部、packed 和 generated 图片。输入 SHALL 采用任务开始时的当前像素快照。

#### Scenario: An HDR still is submitted
- **WHEN** 用户对可读的 EXR、HDR 或其他浮点静态图片执行 Remove Background
- **THEN** 系统捕获当前 RGBA、尺寸与颜色解释，并提交普通 RGB 识别预览

#### Scenario: Unsaved pixels are present
- **WHEN** 源浮点图包含未保存的像素编辑
- **THEN** 识别预览与最终 RGB 均使用当前编辑后的快照

#### Scenario: An HDR animation is submitted
- **WHEN** 用户对 HDR 序列或浮点动画执行 Remove Background
- **THEN** 系统在创建推理任务前提示本次 HDR 功能支持静态图，并保持源图状态

### Requirement: Deterministic recognition preview

系统 SHALL 通过确定性的曝光范围压缩及色彩编码生成 BEN2 的普通 RGB 预览，原始 RGB SHALL 独立保留。预览 SHALL 正确解释源 alpha，且不受用户显示变换设置影响。

#### Scenario: Highlights exceed one
- **WHEN** 源图包含多个大于 1 的不同亮度值
- **THEN** 预览先进行色调映射再编码，原始快照保留这些数值

#### Scenario: Display settings change
- **WHEN** 相同源像素分别在不同 View Transform、Look 或 Exposure 下提交
- **THEN** 识别预览一致

#### Scenario: The image is black or contains negative values
- **WHEN** 可读源像素为全黑或包含有限负颜色值
- **THEN** 预览数值有限，源 RGB 不因预览映射改变

### Requirement: Float alpha result

HDR 去背景 Job SHALL 返回原始尺寸的 float32 alpha 数组，数值有限且位于 0–1。系统 SHALL 在使用前验证产物。

#### Scenario: BEN2 predicts a soft edge
- **WHEN** 模型预测连续透明度边缘
- **THEN** alpha 经过浮点缩放返回，合成前不量化为 8-bit

#### Scenario: Alpha is invalid
- **WHEN** alpha 文件损坏、尺寸不符或包含非有限及越界数值
- **THEN** 系统报告结果错误，保持源图片与目标绑定

### Requirement: HDR color and transparency persistence

系统 SHALL 保留源 RGB 的场景线性色彩及动态范围，并以源 alpha 与预测 alpha 的乘积作为结果透明度。结果 SHALL 为同尺寸浮点图像并采用 32-bit float RGBA EXR 持久化，颜色误差 SHALL 限于浮点运算与必要颜色转换的容差。

#### Scenario: Straight alpha is present
- **WHEN** 源图为 straight alpha 且存在大于 1 的 RGB 和部分透明像素
- **THEN** 结果 RGB 保留，alpha 等于源 alpha 乘预测 alpha

#### Scenario: Premultiplied alpha is present
- **WHEN** 源图采用 PREMUL 且包含部分透明及完全透明像素
- **THEN** 系统按 alpha 关联语义合成，边缘颜色正确且结果没有 NaN 或 Inf

#### Scenario: The project is saved and reopened
- **WHEN** 用户保存含处理结果的 blend 文件后重新打开
- **THEN** 结果尺寸、HDR 数值、颜色解释和透明度保持一致

### Requirement: Transactional target update

系统 SHALL 复用既有图片目标提交规则，保护共享使用者并支持撤销、重做与错误恢复。Blender 数据访问 SHALL 发生于主线程，任务通信 SHALL 使用可序列化普通参数。

#### Scenario: Another owner shares the image
- **WHEN** 源图片存在其他实际使用者
- **THEN** 仅发起操作的目标取得独立 HDR 结果，其他使用者仍引用原图

#### Scenario: The source changes during inference
- **WHEN** 原目标失效、改绑图片或源像素与颜色解释发生修改
- **THEN** 系统拒绝覆盖当前状态，提示重新执行并清理本次临时资源

#### Scenario: The operation is cancelled or fails
- **WHEN** 准备、推理、合成或提交取消或失败
- **THEN** 系统保持或恢复源图及目标绑定，释放本次快照和临时数据

#### Scenario: The user undoes and redoes
- **WHEN** 用户撤销并重做一次成功的 HDR 去背景
- **THEN** 原始和处理后的浮点内容及绑定正确恢复，重做无需重新推理

### Requirement: Existing media behavior

系统 SHALL 保留普通图片、视频和普通序列的现有去背景行为，所有 BEN2 消费者 SHALL 适配统一的数值 alpha 核心。

#### Scenario: An existing regular image or animation is processed
- **WHEN** 用户提交现有支持的普通图片或动画
- **THEN** 系统按既有帧选择、透明度合成和输出规则完成操作

