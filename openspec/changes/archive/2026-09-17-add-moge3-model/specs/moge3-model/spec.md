## Purpose

让用户通过现有 ONNX Runtime 体系使用完整的 MoGe-3 ViT-L 几何预测，使模型准备、选择和执行在深度平面、裁切与全景中具有一致行为，并通过完整细化及数值验证保证结果可信。

## ADDED Requirements

### Requirement: Execute complete MoGe 3 with ONNX

正式推理 SHALL 通过 ONNX Runtime 执行 MoGe 3 的学习网络计算，并完成三次细化；运行环境 SHALL 无需 PyTorch、FlexGEMM 或 Triton。

#### Scenario: Production inference
- **WHEN** 在仅安装声明的 ONNX 运行依赖的 Server 中执行 MoGe 3
- **THEN** 完成包含三次细化的预测，不依赖外部 Torch 环境或服务

### Requirement: Validate conversion before availability

系统 SHALL 在完整流程的动态尺寸、分辨率等级、精度、性能和执行提供程序验证通过后才将新模型登记为正式可用模型。

#### Scenario: Incomplete conversion
- **WHEN** 只有关闭细化的模型可以运行，或完整模型未通过预定数值验收
- **THEN** 保留验证结果且不将其作为完整 MoGe 3 发布

### Requirement: Select and prepare model

系统 SHALL 提供 MOGE3_VITL 选项，保留已有模型键和默认值，下载并校验推理所需的全部 ONNX 资产。

#### Scenario: Download success
- **WHEN** 所需图文件及外部权重全部下载并通过完整性校验
- **THEN** 标记模型就绪，深度平面、裁切与全景使用用户所选模型

#### Scenario: Interrupted download
- **WHEN** 下载失败、取消或文件不完整
- **THEN** 不标记就绪，并允许重新准备

### Requirement: Preserve geometry contract

MoGe 3 SHALL 按所选分辨率等级提供与分析图尺寸对应的深度、法线、有效性、点图和相机内参，并遵循既有源 Alpha 处理契约。

#### Scenario: Image inference
- **WHEN** 有效图片完成推理
- **THEN** 有效区域深度为有限正值，产物可供既有几何工作流应用

#### Scenario: Panorama inference
- **WHEN** 全景任务选择 MoGe 3
- **THEN** 透视视图使用已知 90 度水平 FOV，模型 Mask 与源有效性共同约束融合及 Alpha 输出

### Requirement: Reuse existing input and workflow controls

MoGe 3 SHALL 沿用 MoGe 2 的输入准备、最大分析尺寸、分辨率等级及设备选择流程。同一组已下载模型资产 SHALL 接受现有流程产生的不同图片尺寸、宽高比和分辨率等级，输出尺寸对应分析图片。

#### Scenario: Vary image dimensions
- **WHEN** 用户连续提交现有输入流程支持的不同尺寸和宽高比图片
- **THEN** 使用同一组模型资产完成预测，遵循现有分析尺寸限制及输出尺寸契约

#### Scenario: Change resolution level
- **WHEN** 用户修改现有 MoGe Resolution Level 后再次执行任务
- **THEN** 新任务采用对应 token 数并执行三次细化，复用已下载模型资产

#### Scenario: Switch to MoGe 3 in an existing workflow
- **WHEN** 用户在深度平面、裁切或全景工作流中将模型改为 MoGe 3
- **THEN** 沿用原有任务参数、操作步骤与几何产物，模型内部完成多图及细化调度

### Requirement: Manage supported sessions

系统 SHALL 按已验证的 ONNX 设备能力执行，复用连续帧或视图的会话，在模型切换及关闭时释放资源，对不支持的执行方式和推理失败给出明确反馈。

#### Scenario: Model switching
- **WHEN** 用户在 MoGe 2 与 MoGe 3 之间切换
- **THEN** 执行新选择并释放旧模型资源

#### Scenario: Unsupported execution or cancellation
- **WHEN** 执行设备不支持、资源不足或任务取消
- **THEN** 给出明确状态，不应用部分结果，并允许后续重新运行
