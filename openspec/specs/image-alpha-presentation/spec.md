# image-alpha-presentation Specification

## Purpose
TBD - created by archiving change enable-image-alpha-blending-and-premul. Update Purpose after archive.
## Requirements
### Requirement: Image Empty results enable alpha blending

AnyImage SHALL 为新建的 Reference Image Empty 及成功提交图片编辑结果的 Image Empty 设置 `use_empty_image_alpha = True`，并保留对象原有整体不透明度与深度设置。

#### Scenario: An alpha editing operation succeeds

- **WHEN** Mask、Frame、Rectify 或 Remove Background 成功替换 Image Empty 图片
- **THEN** 承载结果的 Empty SHALL 开启 Alpha Blending
- **AND** 对象 `color[3]` 与 `empty_image_depth` SHALL 保持原值

#### Scenario: A reference image is pasted

- **WHEN** AnyImage 新建剪贴板 Reference Image Empty
- **THEN** 对象 SHALL 默认开启 Alpha Blending

#### Scenario: Editing is cancelled or fails

- **WHEN** 用户取消手势或结果提交失败
- **THEN** 原 Image 和 Empty Alpha Blending 状态 SHALL 保持或恢复到操作前

### Requirement: Edited color images default to PREMUL

AnyImage SHALL 将本地图片编辑结果及公共图片编辑 Job 加载结果的最终 `Image.alpha_mode` 设置为 `PREMUL`。该默认值 SHALL 在成功交付后生效，SHALL NOT 依赖源图片原模式。

#### Scenario: Local alpha editing creates a packed result

- **WHEN** Mask、Frame 或 Rectify 从 STRAIGHT、CHANNEL_PACKED 或 PREMUL 源创建结果
- **THEN** 结果 Image SHALL 使用 PREMUL 并保留现有 Pack 规则

#### Scenario: A background removal result is loaded

- **WHEN** Remove Background 或共享图片编辑结果加载入口的 Upscale 返回 RGBA 图片
- **THEN** 加载结果 SHALL 使用 PREMUL
- **AND** 序列结果 SHALL 保留原有帧映射、播放范围及逐帧像素内容

### Requirement: Alpha presentation preserves editable pixel content

Alpha 呈现默认值 SHALL 保留既有业务编辑算法产出的 RGB 与 Alpha 数值，包括完全透明 RGB，并 SHALL 保证 Pack、保存重载和重复编辑后仍可读取与恢复这些内容。系统 SHALL NOT 为设置 PREMUL 而永久清除透明 RGB 或重复乘入 Alpha。

#### Scenario: Mask Add restores hidden color after reload

- **WHEN** 图片经过 Mask Subtract、结果 Pack、blend 保存重开，再执行 Mask Add
- **THEN** 恢复区域 SHALL 保留原隐藏 RGB，误差仅限既有编码精度
- **AND** 结果 SHALL 继续使用 PREMUL

#### Scenario: A PREMUL result is framed again

- **WHEN** PREMUL 结果以像素对齐映射再次执行 Frame
- **THEN** RGB 和 Alpha SHALL 符合 Frame 图层合成与边界覆盖采样规则
- **AND** 模式设置 SHALL 不导致额外 Alpha 相乘或颜色衰减

#### Scenario: Foreground alpha is restored over a white bottom image

- **WHEN** 当前 Frame 合成包含透明白色底图及 Alpha 渐变前景，随后恢复结果 Alpha
- **THEN** RGB SHALL 保留前景到白色的连续混合
- **AND** Alpha SHALL 沿用当前独立合成与编辑公式

#### Scenario: Packed pixels and exported PNG are inspected

- **WHEN** 检查 byte buffer 编辑结果、浮点源派生结果及加载的 PNG 结果
- **THEN** 操作前后、Pack 和导出重载后的业务 RGB/Alpha SHALL 在约定编码精度内一致

### Requirement: Mesh Color images use PREMUL independently of data textures

AnyImage 为 Plane、Depth Plane 及 Cutout 创建的材质 SHALL 将 Color Image 配置为 PREMUL，并保持独立 Color/Alpha 连线及当前材质透明策略。Depth 和 Normal Image SHALL 保留各自数据通道、Alpha 模式与颜色空间约定。

#### Scenario: A local mesh uses copied or cropped color

- **WHEN** Plane 使用源图片副本或 Cutout 使用裁剪 Color 图片构建材质
- **THEN** Color Image SHALL 为 PREMUL
- **AND** 构建过程 SHALL 保留既有 Color 像素及颜色空间策略

#### Scenario: AI geometry uses generated textures

- **WHEN** Depth Plane 或 Cutout 加载 AI Color、Depth 和 Normal 结果
- **THEN** Color Image SHALL 为 PREMUL
- **AND** Depth 与 Normal SHALL 保留原有数据解释方式

#### Scenario: Source images have other users

- **WHEN** 被编辑或转换的源 Image 同时被未参与的对象引用
- **THEN** 模式设置 SHALL 作用于结果 Image 或独立 Color 副本
- **AND** 未参与对象引用的源 Image 模式与像素 SHALL 保持不变

### Requirement: Defaults are applied at operation boundaries

AnyImage SHALL 在新建或成功交付范围内应用本策略，SHALL NOT 在注册、加载场景或普通重绘时批量修改已有图片。

#### Scenario: An existing scene is opened

- **WHEN** 用户打开含有已有 Image Empty 和材质的场景
- **THEN** 未参与 AnyImage 新操作的图片及对象设置 SHALL 保持原样

