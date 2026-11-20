# color-match-srgb-preview Specification

## Purpose
规定参考图和目标图的像素解释。用户在目标对象或纹理节点上调整色彩与亮度时，临时图片显示匹配效果，确认后以原尺寸和原色彩设置提交结果。

## Requirements

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

### Requirement: Match Color previews the target in place

Match Color SHALL 在目标上显示临时图片，保留原图的宽高比、像素方向、色彩空间和 Alpha 模式。编辑器和视图按当前显示设置呈现预览。

#### Scenario: An object uses a shared material
- **WHEN** 从对象入口调整共享材质中的颜色
- **THEN** 只有该对象显示临时预览，其他对象继续使用原材质

#### Scenario: A shader texture is previewed
- **WHEN** 从着色器编辑器调整活动纹理节点
- **THEN** 该节点显示预览，使用该节点的材质或世界环境同步显示结果

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

系统 SHALL 在确认、取消、初始化失败与刷新失败时释放临时图片、为对象预览创建的材质、绘制回调和定时器。预览期间 SHALL 保留源图像素。

#### Scenario: A preview is cancelled or fails
- **WHEN** 用户取消操作，或预览初始化、刷新发生异常
- **THEN** 恢复仍属于这次预览的绑定，保留源图内容和用户重新指定的绑定

#### Scenario: A preview refreshes repeatedly
- **WHEN** 用户连续调整预览
- **THEN** 复用同一张临时图片刷新像素，结束后释放预览资源
