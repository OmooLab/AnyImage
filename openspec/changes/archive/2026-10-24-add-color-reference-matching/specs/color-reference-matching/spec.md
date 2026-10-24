## ADDED Requirements

### Requirement: Current scene stores one color reference
系统 SHALL 允许用户从当前有效图片目标执行 `Set Color Reference`，并在当前 Scene 中持续保存该静态 Image 作为唯一颜色参考。再次设置 SHALL 替换此前参考，且 MUST NOT 修改参考图片内容。

#### Scenario: A reference is set from an image context
- **WHEN** 用户在 Image Empty、可解析 Color Image 的 AnyImage Mesh 或材质 Image Texture 上执行 `Set Color Reference`
- **THEN** 当前 Scene 的颜色参考指向该 Image，图片像素和使用者保持不变

#### Scenario: The reference is replaced
- **WHEN** 当前 Scene 已有颜色参考且用户从另一有效图片再次执行 `Set Color Reference`
- **THEN** 新 Image 成为唯一颜色参考，旧 Image 不再作为后续匹配来源

#### Scenario: An animated image is selected as reference
- **WHEN** 当前目标为 Movie、Sequence 或其他动画图片
- **THEN** `Set Color Reference` 不可执行，当前颜色参考保持不变

### Requirement: Matching requires one valid reference and target
系统 SHALL 仅在当前 Scene 存在有效静态颜色参考且当前上下文可解析不同的有效静态目标 Image 时允许执行 `Match Color Reference`。系统 MUST NOT 在参考缺失或失效时回退到其他图片。

#### Scenario: No reference exists
- **WHEN** 当前 Scene 尚未设置颜色参考
- **THEN** `Match Color Reference` 显示为不可执行且不修改任何图片

#### Scenario: The stored reference is unavailable
- **WHEN** 已保存的参考 Image 被移除、不可读取或不再是静态图片
- **THEN** `Match Color Reference` 不可执行且不选择其他 Image 作为参考

#### Scenario: A valid reference and target exist
- **WHEN** 当前 Scene 存在有效静态参考且当前上下文解析出另一有效静态目标
- **THEN** `Match Color Reference` 可执行并以保存的 Image 作为唯一参考

#### Scenario: The target is the reference image
- **WHEN** 当前目标与保存的参考是同一 Image 数据块
- **THEN** `Match Color Reference` 不可执行

### Requirement: Matching applies one fixed complete color transform
系统 SHALL 以固定完整强度将参考 Image 的整体亮度分布和色度特征迁移到目标 RGB，同时保持目标尺寸、Alpha、构图、纹理和空间结构。操作 MUST NOT 提供 Strength、Tone、Color、模式或背景处理属性。

#### Scenario: A target is matched
- **WHEN** 用户执行 `Match Color Reference`
- **THEN** 系统完整应用校准后的确定性颜色变换，并且 Operator 调整面板不提供颜色匹配参数

#### Scenario: The same inputs are matched again
- **WHEN** 未改变的参考像素与目标像素再次执行匹配
- **THEN** 系统生成像素等价的结果，不引入随机内容或结构变化

### Requirement: Matching controls gradients, compression noise and gamut
系统 SHALL 使用单调平滑亮度变换、受限色度映射、平滑调整场和色域压缩，避免将低频渐变转换为明显色阶，并避免放大目标边缘的压缩噪声。byte 结果 SHALL 仅在最终量化时使用确定性抖动。

#### Scenario: The target contains a smooth gradient
- **WHEN** 目标包含天空、摄影棚背景或其他连续低频渐变
- **THEN** 匹配结果保持连续过渡，不产生由颜色变换新增的明显分段

#### Scenario: The target contains JPEG edge noise
- **WHEN** 目标轮廓附近含有轻微 JPEG 块或振铃
- **THEN** 颜色调整不以高增益放大该误差，且主体细节保持清晰

#### Scenario: A mapped color exceeds the output gamut
- **WHEN** 完整颜色变换产生超出目标 RGB 色域的颜色
- **THEN** 系统平滑压缩色度后输出，而不是逐通道硬裁剪该颜色

### Requirement: Reference Alpha defines feature extraction
系统 SHALL 在设置或使用颜色参考时按参考 Alpha 对颜色特征提取加权，并忽略完全透明参考像素。匹配目标时系统 SHALL 对整张目标图片的全部 RGB 应用相同颜色迁移，包括完全透明像素下的隐藏 RGB，并 SHALL 原样保留目标 Alpha。没有有效 Alpha 的参考 SHALL 使用全部 RGB，系统 MUST NOT 启用背景识别或分割。

#### Scenario: Reference contains Alpha
- **WHEN** 参考包含透明及半透明像素
- **THEN** 参考颜色特征按可见度加权提取，完全透明参考像素不影响迁移特征

#### Scenario: Target contains Alpha
- **WHEN** 目标包含可见、半透明和完全透明像素
- **THEN** 系统迁移全部目标 RGB，包括完全透明像素下的隐藏 RGB，并保持每个像素的 Alpha 不变

#### Scenario: Reference or target has no Alpha
- **WHEN** 参考或目标是不含有效 Alpha 的 RGB 图片
- **THEN** 系统对其全部 RGB 执行对应的特征提取或颜色迁移，不执行平坦背景检测、主体分割或背景保留

### Requirement: Color matching is a local non-AI image edit
系统 SHALL 使用已有 NumPy/SciPy 能力在 Blender 侧完成颜色匹配，且 MUST NOT 要求 AI 环境、模型下载、推理设备或 Job Server 可用。

#### Scenario: AI environment is not installed
- **WHEN** 有效参考和目标存在但 AI 环境尚未安装
- **THEN** `Set Color Reference` 与 `Match Color Reference` 仍可执行

### Requirement: Matching uses transactional image replacement
系统 SHALL 通过现有图片编辑事务提交颜色匹配结果，保持目标 Owner、节点连接、图片解释设置及共享用户隔离。成功匹配 SHALL 作为一次 Undo 恢复，失败 SHALL 保持目标和参考不变。

#### Scenario: Matching succeeds
- **WHEN** 颜色变换与结果提交完成
- **THEN** 当前目标使用匹配结果，参考 Image 和其他共享用户保持不变

#### Scenario: Matching fails before commit
- **WHEN** 像素读取、颜色变换或结果创建失败
- **THEN** 系统释放临时结果并保持参考和目标的内容与绑定不变

#### Scenario: The user undoes a match
- **WHEN** 用户撤销一次成功的 `Match Color Reference`
- **THEN** 目标内容或绑定恢复到匹配前状态，颜色参考仍保持设置
