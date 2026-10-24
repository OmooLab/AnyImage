## MODIFIED Requirements

### Requirement: Matching applies one fixed complete color transform
系统 SHALL 使用内置 NumPy 平滑 HM–MKL–HM 算法计算完整匹配结果，并以单一 Mix 在原图与该结果之间混合。两次 HM SHALL 平滑累计分布映射曲线并限制其为单调有限斜率，不得模糊图片或使用空间邻域。相同输入 SHALL 产生确定性结果，保持目标尺寸、Alpha 和像素位置。系统 MUST NOT 提供算法模式或独立 Tone/Color/Lightness 参数。

#### Scenario: A target is matched
- **WHEN** 用户使用有效参考匹配目标
- **THEN** 系统依次执行平滑 HM、MKL、平滑 HM，并按当前 Mix 提交结果

#### Scenario: The same inputs are matched again
- **WHEN** 输入像素、参考准备规则和 Mix 相同
- **THEN** 输出像素等价且不引入随机内容

### Requirement: Color matching is a local non-AI image edit
系统 SHALL 在 Blender 侧使用 NumPy 内置实现完成迁移，MUST NOT 导入或要求安装 color-matcher。materialyoucolor 与 Pillow SHALL 用于参考色板相关能力；操作 SHALL 在 AI 环境、模型与 Job Server 不可用时正常工作。

#### Scenario: The color-matcher package is absent
- **WHEN** 已安装插件声明的运行依赖但没有 color-matcher 或 AI 环境
- **THEN** 用户仍可设置参考、查看色板和完成匹配

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Matching controls gradients, compression noise and gamut
**Reason**: 输出由固定平滑 HM–MKL–HM 与直接 Mix 定义。
**Migration**: 删除旧平滑调整场、独立亮度映射、色域压缩和抖动路径，按新的输出规则验证结果。

### Requirement: Color matching uses an adaptive spatial color signature
**Reason**: HM–MKL–HM 使用颜色分布与协方差，不使用迁移签名。
**Migration**: 移除空间显著签名、8–16 锚点及对应传输求解，色板改用 Material 提取。
