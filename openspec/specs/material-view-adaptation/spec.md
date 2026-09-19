# material-view-adaptation Specification

## Purpose
TBD - created by archiving change configure-material-view-adaptation. Update Purpose after archive.
## Requirements
### Requirement: Preferences expose material view adaptation

AnyImage SHALL 在 Preferences 的 Shading 分组提供 `Adapt to Scene View Transform` 布尔选项，默认关闭。扩展设置及读取入口 SHALL 位于 `preferences.py`，并通过 `addon_preferences()` 读取。

#### Scenario: Preferences use the default

- **WHEN** 用户尚未设置该选项或读取不到扩展偏好
- **THEN** 材质颜色贴图 SHALL 使用关闭适配的行为

### Requirement: Material color space determines alpha presentation

开启适配时，AnyImage SHALL 按当前场景 View Transform 选择既有映射中的 inverse 颜色空间，并使用 STRAIGHT。关闭适配时 SHALL 使用 sRGB + PREMUL。实际回退为 sRGB 时 SHALL 使用 PREMUL，并保持 Preferences 中的适配开关原值。

#### Scenario: A supported view is adapted

- **WHEN** 适配开启，当前场景为 AgX，且 `AgX Base sRGB` 可用
- **THEN** 材质 Color Image SHALL 使用 `AgX Base sRGB` + STRAIGHT

#### Scenario: Other mapped views are adapted

- **WHEN** 适配开启，场景使用 ACES 1.3、ACES 2.0、Filmic 或 Khronos PBR Neutral，且对应空间可用
- **THEN** Color Image SHALL 分别使用 `ACES 1.3 sRGB`、`ACES 2.0 sRGB`、`Filmic sRGB` 或 `Khronos PBR Neutral sRGB`
- **AND** Alpha 模式 SHALL 为 STRAIGHT

#### Scenario: Adaptation is disabled

- **WHEN** 适配关闭，创建任意受支持入口的材质
- **THEN** Color Image SHALL 使用 sRGB + PREMUL

#### Scenario: The scene resolves to sRGB

- **WHEN** 适配开启，但场景为 Standard、视图未匹配、场景不可用或 inverse 空间不被支持
- **THEN** Color Image SHALL 使用 sRGB + PREMUL

#### Scenario: The fallback color space is unavailable

- **WHEN** 所需颜色空间及 sRGB 均无法应用
- **THEN** 配置 SHALL 明确报错并保留贴图之前的有效配置
- **AND** Preferences 中的适配开关 SHALL 保持原值

### Requirement: Material entry points apply the same policy

AnyImage SHALL 在 Plane、Depth Plane、Cutout 和剪贴板 Mesh 材质创建时统一配置 Color Image。最终模式 SHALL 在后续绑定及交付步骤中保留。Depth 与 Normal SHALL 保留各自的数据解释约定。

#### Scenario: A material is created from an edited color result

- **WHEN** 一个 PREMUL 编辑结果进入开启适配的 inverse 材质
- **THEN** 最终材质 Color Image SHALL 为 STRAIGHT
- **AND** 材质交付后 SHALL 保留该模式

#### Scenario: Shadeless material is created

- **WHEN** 用户通过支持 Shadeless 的入口创建材质
- **THEN** Color Image SHALL 应用相同颜色空间与 Alpha 配对策略

### Requirement: Configuration preserves business pixels and source ownership

材质 Color 配置 SHALL 保留原有业务 RGB、Alpha 和完全透明区域 RGB，并在 Pack、保存重载和再次编辑后保持可读取。配置 SHALL 作用于材质专用 Color Image 或独立 Color 副本。

#### Scenario: The source image has other users

- **WHEN** 源 Image 同时被其他对象引用
- **THEN** 配置 SHALL 作用于独立 Color 结果
- **AND** 原 Image 的颜色空间、Alpha 模式和业务像素 SHALL 保持原值

#### Scenario: A color result is packed and reopened

- **WHEN** byte、float、generated、dirty 或 packed 来源的 Color 完成配置并保存重载
- **THEN** 业务 RGB/Alpha SHALL 在既有编码精度内保留
- **AND** 结果 SHALL 保持所选颜色空间和 Alpha 模式

### Requirement: Preferences exclusively control material adaptation

Preferences SHALL 是适配开关的唯一控制来源。新建材质 SHALL 读取当前偏好；已创建的材质颜色贴图 SHALL 保留原配置。创建操作和颜色空间解析 SHALL 保持偏好值。

#### Scenario: The preference changes

- **WHEN** 用户在 Preferences 开启或关闭适配
- **THEN** AnyImage 已创建的材质颜色贴图 SHALL 保持原颜色空间、Alpha 模式和像素
- **AND** 后续新建材质 SHALL 使用新的偏好设置

#### Scenario: A new material shares its source with an existing material

- **WHEN** 切换偏好后，使用已被现有材质引用的源 Image 创建新材质
- **THEN** 新材质 SHALL 使用独立 Color Image 并应用当前偏好
- **AND** 已有材质的贴图及其配置 SHALL 保持原值

#### Scenario: A material is created or an inverse space is unavailable

- **WHEN** 创建材质或颜色空间解析发生回退
- **THEN** Preferences 中的适配开关 SHALL 保持操作前的值

### Requirement: Adaptation affects only material color textures

本选项 SHALL 仅配置 AnyImage 材质的 Color 贴图。Empty、普通图片编辑结果、Depth、Normal 和非目标材质 SHALL 保持原有行为与数据。

#### Scenario: A material color image is shared with an Empty

- **WHEN** 新建材质的源 Color Image 同时被 Empty 引用
- **THEN** 系统 SHALL 为材质 Color 创建独立副本并重新绑定目标节点
- **AND** Empty 引用的原 Image 的颜色空间、Alpha 模式与业务像素 SHALL 保持原值

#### Scenario: Ordinary image editing runs with adaptation enabled

- **WHEN** 开启适配后执行 Mask、Frame、Rectify 或图片编辑 Job
- **THEN** 编辑结果 SHALL 沿用各自已有颜色空间与 Alpha 规则

