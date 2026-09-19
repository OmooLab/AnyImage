## Purpose

为深度生成、图片超分和背景移除提供各三款用途明确的正式模型，使偏好选择、首次安装、模型下载和服务就绪状态表达相同的模型集合，并让新用户以轻量模型开始使用。

## ADDED Requirements

### Requirement: 三类模型采用固定三档集合
系统 SHALL 按以下顺序提供九款正式模型：Depth 为 MoGe-2 ViT-S Normal、MoGe-2 ViT-B Normal、MoGe-3 ViT-L；Upscale 为 Real-ESRGAN General WDN x4v3、Real-ESRGAN x4plus、Real HAT GAN x4 Sharper；Background 为 BiRefNet Lite、BEN2、BiRefNet HR-matting。各类别第一项 SHALL 为新偏好的默认值。

#### Scenario: 查看模型选项
- **WHEN** 用户查看偏好或模型下载列表
- **THEN** 每个类别恰好显示上述三款模型，顺序一致，模型名、用途、许可证和下载体积对应实际资源

#### Scenario: 服务离线时显示目录
- **WHEN** 服务尚未启动而界面需要展示模型
- **THEN** 本地目录与服务启动后返回的正式模型集合一致

### Requirement: 首次安装仅要求三个默认模型
系统 SHALL 将 MoGe-2 ViT-S Normal、General WDN x4v3 和 BiRefNet Lite 作为默认环境初始化所需的模型集合，其他模型按用户选择下载。

#### Scenario: 新安装完成初始化
- **WHEN** 推理环境和三个默认模型都已就绪，其他六款尚未下载
- **THEN** AI 初始化状态为就绪，默认功能可运行

#### Scenario: 选择未下载的高档模型
- **WHEN** 用户执行功能时选中的非默认模型尚未就绪
- **THEN** 系统指出需要下载该模型，不使用其他模型替代本次请求

### Requirement: 有效偏好保留且退役选择明确处理
系统 SHALL 保留仍属于所选类别的持久化模型键，并将退役或无效的偏好值归一为类别默认值；服务收到未知或退役模型键时 SHALL 返回明确错误。

#### Scenario: 用户已有 BEN2 偏好
- **WHEN** 更新后读取有效的 BEN2 背景移除选择
- **THEN** 继续选择 BEN2

#### Scenario: 用户已有 PiSA-SR 偏好
- **WHEN** 更新后读取已退役的 PiSA-SR 超分选择
- **THEN** 当前有效选择为 General WDN x4v3，界面与后续请求一致

#### Scenario: 旧请求直接指定退役模型
- **WHEN** 服务收到指定 DA3、MoGe-2 L、SAFMN 或 PiSA-SR 的请求
- **THEN** 返回未知或不可用模型错误，不加载或下载退役资源
