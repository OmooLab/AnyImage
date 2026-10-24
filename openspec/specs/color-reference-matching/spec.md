# color-reference-matching Specification

## Purpose
定义场景参考图驱动的本地颜色匹配流程，涵盖参考与目标校验、颜色变换、参考准备复用、透明度语义和图片结果的事务提交。

## Requirements

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
系统 SHALL 使用内置 NumPy 平滑 HM–MKL–HM 算法计算完整匹配结果，并以单一 Mix 在原图与该结果之间混合。两次 HM SHALL 平滑累计分布映射曲线并限制其为单调有限斜率，不得模糊图片或使用空间邻域。相同输入 SHALL 产生确定性结果，保持目标尺寸、Alpha 和像素位置。系统 MUST NOT 提供算法模式或独立 Tone/Color/Lightness 参数。

#### Scenario: A target is matched
- **WHEN** 用户使用有效参考匹配目标
- **THEN** 系统依次执行平滑 HM、MKL、平滑 HM，并按当前 Mix 提交结果

#### Scenario: The same inputs are matched again
- **WHEN** 输入像素、参考准备规则和 Mix 相同
- **THEN** 输出像素等价且不引入随机内容

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
系统 SHALL 在 Blender 侧使用 NumPy 内置实现完成迁移，MUST NOT 导入或要求安装 color-matcher。materialyoucolor 与 Pillow SHALL 用于参考色板相关能力；操作 SHALL 在 AI 环境、模型与 Job Server 不可用时正常工作。

#### Scenario: The color-matcher package is absent
- **WHEN** 已安装插件声明的运行依赖但没有 color-matcher 或 AI 环境
- **THEN** 用户仍可设置参考、查看色板和完成匹配

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

### Requirement: Reference preparation is reused across matches
系统 SHALL 在选择参考时准备色板和迁移参考数据，并在内容未变时跨 Match 调用复用。有效缓存命中 SHALL 不读取参考全图或重复提取统计。参考身份或内容变化、清除和插件注销 SHALL 使对应缓存失效，准备失败 SHALL 清除不可用的准备状态。

#### Scenario: Multiple targets use the same reference
- **WHEN** 参考未变且准备结果有效，用户依次匹配多个目标
- **THEN** 每次 Match 仅准备目标相关数据并复用参考统计

#### Scenario: Reference pixels change
- **WHEN** 参考被编辑、重载、Undo 恢复或替换
- **THEN** 后续匹配使用更新后的数据且不会复用旧颜色统计

#### Scenario: A saved scene has no runtime cache
- **WHEN** 打开文件后参考有效但运行时缓存不存在
- **THEN** 首次需要时准备一次，随后匹配复用该结果
