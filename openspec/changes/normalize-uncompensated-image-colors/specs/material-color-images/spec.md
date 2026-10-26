## MODIFIED Requirements

### Requirement: Encoding preserves color precision and presentation

颜色图准备 SHALL 保留对应范围的 RGB、Alpha、透明区域 RGB 及源编码精度，float / HDR SHALL 保留浮点范围。普通 byte 材质 SHALL 按当前偏好应用 inverse 解释或 `image-color-normalization` 规定的固定归一化 sRGB；归一化 SHALL 原地更新已准备的 `_color`。所有 float / HDR 材质 SHALL 保留源颜色空间与 Alpha 模式。

#### Scenario: Ordinary material is configured

- **WHEN** 普通 byte 材质匹配可用 inverse 空间
- **THEN** 开启补偿 SHALL 采用 inverse + STRAIGHT；关闭补偿 SHALL 原地完成 固定归一化，采用 sRGB + PREMUL
- **AND** 原图设置与像素 SHALL 保持不变，当前 `_color` Image 身份 SHALL 保持不变

#### Scenario: Material color resolves to sRGB

- **WHEN** 场景解析或回退为直接 sRGB
- **THEN** 颜色图 SHALL 采用 sRGB + PREMUL 并保留业务像素

#### Scenario: HDR and unsaved pixels are serialized

- **WHEN** float / HDR、generated、dirty 或 packed 源图完成颜色图生成、配置、打包和保存重载
- **THEN** 结果 SHALL 在对应编码精度内保留最终业务像素、动态范围与选定的颜色解释
- **AND** 所有 float / HDR 材质 SHALL 保留源图颜色空间与 Alpha 模式；Panorama 非 sRGB 分支沿用源解释

#### Scenario: Float source interpretation prevents lossless serialization

- **WHEN** 按源颜色空间和 Alpha 模式解码 EXR 后无法保留源浮点像素
- **THEN** 操作 SHALL 明确拒绝转换，清理临时资源并保持源图不变
- **AND** float / HDR 材质 SHALL 不启用场景视图适配的 Alpha Fix

#### Scenario: A normalized source prepares another color image

- **WHEN** 已完成 固定归一化的图像进入材质颜色准备流程
- **THEN** 新 `_color` SHALL 保留该图的当前 sRGB 像素及已归一化状态
- **AND** 后续材质配置 SHALL 不重复归一化
