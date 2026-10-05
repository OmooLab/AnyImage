## ADDED Requirements

### Requirement: Color matching uses a fixed pixel interpretation

Match Color SHALL 将 byte 图片当前业务 RGB 按 sRGB 解码到 linear Rec.709，将 float 图片当前业务 RGB 按 linear Rec.709 使用。参考准备、色板、参考图标、代理匹配与全分辨率匹配 SHALL 使用相同约定，Alpha SHALL 保留原语义。

#### Scenario: Byte images have different color space settings
- **WHEN** 两份 byte 图片的业务 RGBA 相同，分别设置为 `sRGB` 和 `AgX Base sRGB` 或自定义 color space
- **THEN** 在相同参考与参数下得到等价的匹配输入、预览及输出像素

#### Scenario: A float image is matched
- **WHEN** 目标或参考是 float 图片
- **THEN** 对应 RGB 直接按 linear Rec.709 处理，并保留已有 float 匹配范围策略

#### Scenario: A reference palette is prepared
- **WHEN** 系统准备参考图标、色板和迁移数据
- **THEN** 三者采用同一像素解释，参考原有设置和内容保持不变

### Requirement: The overlay displays fixed sRGB pixels

Match Color 浮层 SHALL 将匹配后的 linear Rec.709 RGB 编码为 sRGB 并限制在显示范围，使用独立 GPU 纹理显示。显示 SHALL 与目标及参考的 Image color space 名称解耦，保留代理宽高比、方向、透明呈现与现有刷新限制。

#### Scenario: A material color image is previewed
- **WHEN** 用户对具有材质 color space 设置的 `_color` 图片启动 Match Color
- **THEN** 浮层按固定 sRGB 显示匹配结果，目标设置与绑定保持原状态

#### Scenario: The OCIO configuration has no sRGB entry
- **WHEN** 用户的 OCIO 配置没有名为 `sRGB` 的色彩空间
- **THEN** 预览直接显示已编码的 sRGB 纹理，正常启动与刷新

#### Scenario: An asymmetric transparent image is previewed
- **WHEN** 预览图片包含不对称图案、透明及半透明像素
- **THEN** 浮层方向正确，透明区域与半透明边缘采用一致的 Alpha 混合

### Requirement: Confirmation preserves the original image interpretation settings

Match Color SHALL 将 byte 结果 RGB 编码为 sRGB，将 float 结果 RGB 保留为线性值，并使用已有图片事务保留目标原 color space、Alpha 模式、尺寸、命名、共享隔离与 Undo 行为。直接执行和交互确认 SHALL 使用同一编码规则。

#### Scenario: A match is confirmed
- **WHEN** 用户确认预览且目标与参考仍有效
- **THEN** 全分辨率结果按对应存储类型编码，保留目标原 color space 和 Alpha 模式，其他共享用户保持原内容

#### Scenario: Zero adjustment is confirmed
- **WHEN** 用户将当前实现的全部匹配调节置零并确认
- **THEN** 原图像素、设置与绑定保持不变

#### Scenario: The image settings change during preview
- **WHEN** 目标 color space 或 Alpha 模式在启动后被外部修改
- **THEN** 系统安全取消提交并保留外部修改

### Requirement: Preview resources follow the modal lifetime

系统 SHALL 在确认、取消、初始化失败与刷新失败时释放该次预览的 GPU 纹理引用、绘制 handler 和 timer。预览 SHALL 保留源图状态，重复刷新 SHALL 保持资源数量有界。

#### Scenario: A preview is cancelled or fails
- **WHEN** 用户取消操作，或预览初始化、刷新发生异常
- **THEN** 源图像素、color space、Alpha 模式与绑定保持原状态，预览资源被释放

#### Scenario: A preview refreshes repeatedly
- **WHEN** 用户连续调整预览
- **THEN** 旧纹理随替换被释放，结束后没有残留预览资源
