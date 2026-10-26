## MODIFIED Requirements

### Requirement: Preferences expose material view adaptation

AnyImage SHALL 在 Preferences 的 Shading 分组提供 `Compensate Image Colors` 布尔选项，默认开启。扩展设置及读取入口 SHALL 位于 `preferences.py`，并通过 `addon_preferences()` 读取。提示 SHALL 说明开启时使用 inverse 补偿，关闭时将适用颜色原地归一化为 sRGB。

#### Scenario: Preferences use the default

- **WHEN** 用户尚未设置该选项或读取不到扩展偏好
- **THEN** 材质与笔刷颜色配置 SHALL 使用开启补偿的行为

### Requirement: Material color space determines alpha presentation

普通 byte 图开启补偿时，AnyImage SHALL 按当前场景 View Transform 选择既有映射中的 inverse 颜色空间并使用 STRAIGHT。关闭补偿且对应 inverse 空间可用时 SHALL 执行 `image-color-normalization` 规定的 固定归一化，再采用 sRGB + PREMUL。解析或回退为 sRGB 时 SHALL 采用 sRGB + PREMUL，并保持 Preferences 原值。现有 float/HDR 保留源解释。

#### Scenario: A supported view is adapted

- **WHEN** 补偿开启，当前场景为 AgX，且 `AgX Base sRGB` 可用
- **THEN** 材质 Color Image SHALL 使用 `AgX Base sRGB` + STRAIGHT

#### Scenario: Other mapped views are adapted

- **WHEN** 补偿开启，场景使用 ACES 1.3、ACES 2.0、Filmic 或 Khronos PBR Neutral，且对应空间可用
- **THEN** Color Image SHALL 分别使用 `ACES 1.3 sRGB`、`ACES 2.0 sRGB`、`Filmic sRGB` 或 `Khronos PBR Neutral sRGB`
- **AND** Alpha 模式 SHALL 为 STRAIGHT

#### Scenario: Adaptation is disabled

- **WHEN** 补偿关闭，创建材质或配置笔刷，普通 byte 图对应的 inverse 空间可用
- **THEN** 当前目标 Image SHALL 原地完成 inverse 解码、固定归一化与 sRGB 编码，采用 sRGB + PREMUL

#### Scenario: The scene resolves to sRGB

- **WHEN** 场景为 Standard、视图未匹配、场景不可用或 inverse 空间不被支持
- **THEN** Color Image SHALL 使用 sRGB + PREMUL，保持原有业务像素

#### Scenario: The fallback color space is unavailable

- **WHEN** 所需颜色空间及 sRGB 均无法应用
- **THEN** 配置 SHALL 明确报错并保留贴图之前的有效配置
- **AND** Preferences 中的适配开关 SHALL 保持原值

### Requirement: Material entry points apply the same policy

AnyImage SHALL 在 Plane、Depth Plane、Relief Plane、Panorama、Cutout、剪贴板 Plane 及笔刷纹理交付时统一配置适用颜色图。最终模式 SHALL 在后续绑定及交付步骤中保留。Depth 与 Normal SHALL 保留各自的数据解释约定。

#### Scenario: A material is created from an edited color result

- **WHEN** 一个 PREMUL 编辑结果进入开启补偿的 inverse 材质
- **THEN** 最终材质 Color Image SHALL 为 STRAIGHT
- **AND** 材质交付后 SHALL 保留该模式

#### Scenario: Shadeless material is created

- **WHEN** 用户通过支持 Shadeless 的入口创建普通 byte sRGB 颜色材质
- **THEN** Color Image SHALL 应用相同补偿或归一化策略
- **AND** 现有保留源解释的非 sRGB 分支 SHALL 保持其行为

#### Scenario: A brush texture is configured

- **WHEN** 在 Sculpt、Texture Paint 或 Vertex Paint 交付笔刷纹理
- **THEN** 传入 Image SHALL 使用与材质相同的颜色策略并保持 Image 身份
- **AND** 笔刷预览 SHALL 使用处理后的图像

### Requirement: Configuration preserves business pixels and source ownership

补偿开启或解析为直接 sRGB 时，材质 Color 配置 SHALL 保留业务像素；补偿关闭并匹配可用 inverse 时 SHALL 原地提交 固定归一化 RGB，保留 Alpha 与尺寸。材质配置 SHALL 作用于准备流程已生成的独立 `_color`，笔刷配置 SHALL 作用于传入 Image。所有成功结果 SHALL 在 Pack、保存重载和再次编辑后保持可读取。

#### Scenario: The source image has other users

- **WHEN** 材质原始源 Image 同时被其他对象引用
- **THEN** 材质配置 SHALL 作用于已准备的独立 `_color`，保持该 Color Image 身份
- **AND** 原始源 Image 的颜色空间、Alpha 模式和业务像素 SHALL 保持原值

#### Scenario: A color result is packed and reopened

- **WHEN** byte、float、generated、dirty 或 packed 来源的 Color 完成配置并保存重载
- **THEN** 最终业务 RGB/Alpha SHALL 在既有编码精度内保留
- **AND** 结果 SHALL 保持所选颜色空间、Alpha 模式及归一化状态

#### Scenario: A brush image is shared

- **WHEN** 待配置笔刷 Image 同时被其他用户引用
- **THEN** 原地处理 SHALL 更新同一个 Image，各引用 SHALL 看到相同处理结果

### Requirement: Preferences exclusively control material adaptation

Preferences SHALL 是补偿开关的唯一控制来源。新准备的未处理颜色图 SHALL 读取当前偏好；已交付颜色图 SHALL 在偏好变化时保持内容与配置。已经归一化的 Image 再次进入配置入口时 SHALL 保留 sRGB 内容与已处理状态。

#### Scenario: The preference changes

- **WHEN** 用户在 Preferences 开启或关闭补偿
- **THEN** 已创建的材质和笔刷颜色图 SHALL 保持原颜色空间、Alpha 模式和像素
- **AND** 后续由原始输入准备的颜色图 SHALL 使用新的偏好设置

#### Scenario: A new material shares its source with an existing material

- **WHEN** 切换偏好后，从相同原始源 Image 创建新材质
- **THEN** 新材质 SHALL 使用既有准备流程生成的独立 `_color` 并应用当前偏好
- **AND** 已有材质的贴图及其配置 SHALL 保持原值

#### Scenario: A material is created or an inverse space is unavailable

- **WHEN** 创建材质或颜色空间解析发生回退
- **THEN** Preferences 中的适配开关 SHALL 保持操作前的值

### Requirement: Adaptation affects only material color textures

本选项 SHALL 配置 AnyImage 的材质 Color 和笔刷目标 Image。独立的 Empty、普通图片编辑结果、Depth、Normal 和非目标材质 SHALL 保持原有行为与数据；同一笔刷 Image 的共享引用遵循原地更新语义。

#### Scenario: A material color image is shared with an Empty

- **WHEN** 新建材质的原始源 Image 同时被 Empty 引用
- **THEN** 系统 SHALL 使用材质准备流程的独立 `_color` 作为配置目标并绑定目标节点
- **AND** Empty 引用的原 Image 的颜色空间、Alpha 模式与业务像素 SHALL 保持原值

#### Scenario: Ordinary image editing runs with adaptation enabled

- **WHEN** 开启补偿后执行 Mask、Frame、Rectify 或图片编辑 Job
- **THEN** 编辑结果 SHALL 沿用各自已有颜色空间与 Alpha 规则
