# conversion-source-images Specification

## Purpose
TBD - created by archiving change reuse-conversion-source-images. Update Purpose after archive.
## Requirements
### Requirement: Conversion selects images by other Empty references

四种 Convert To SHALL 在应用转换时检查整个 Blender 数据中的其他 Image Empty 是否引用同一源 Image。没有其他引用时 SHALL 复用原 Image；存在时 SHALL 使用原 Image 的独立副本。

#### Scenario: Only the converted Empty uses the source

- **WHEN** 源 Image 没有被其他 Image Empty 引用
- **THEN** 转换材质 SHALL 引用原 Image 数据块并保留其名称和路径

#### Scenario: Another Empty shares the image

- **WHEN** 另一个 Image Empty 引用同一 Image，包括隐藏对象或其他场景对象
- **THEN** 材质 SHALL 使用独立副本，沿用原名并由 Blender 消歧
- **AND** 其他 Empty 的 Image 引用、像素、颜色空间和 Alpha 模式 SHALL 保持原值

#### Scenario: Existing materials share the image

- **WHEN** 原 Image 被材质引用且没有其他 Image Empty 引用
- **THEN** 转换 SHALL 复用原 Image，已有材质 SHALL 同步看到该 Image 的配置变化

#### Scenario: Separate images have the same file path

- **WHEN** 另一 Empty 使用路径相同但数据块不同的 Image
- **THEN** 该引用 SHALL 视为独立图像，转换 SHALL 复用当前源 Image

### Requirement: Conversion preserves material presentation rules

转换 SHALL 对选定的 Image 应用既有材质颜色空间和 Alpha 配对规则，保留业务 RGB、Alpha、透明区域 RGB、精度和未保存像素。Panorama 的 float 或非 sRGB shadeless 图像 SHALL 沿用源颜色空间和 Alpha 模式。

#### Scenario: Standard material adaptation is applied

- **WHEN** 普通转换关闭适配，或所需 inverse 空间回退到 sRGB
- **THEN** 选定 Image SHALL 使用 sRGB + PREMUL

#### Scenario: Inverse adaptation is available

- **WHEN** 普通转换启用适配且对应 inverse 空间可用
- **THEN** 选定 Image SHALL 使用该空间与 STRAIGHT

#### Scenario: Panorama preserves HDR interpretation

- **WHEN** Panorama 源图为 float 或采用现有保留分支匹配的非 sRGB 空间
- **THEN** 材质 Image SHALL 保留原颜色空间、Alpha 模式与 HDR 像素

#### Scenario: Unsaved and packed pixels remain readable

- **WHEN** generated、dirty 或 packed 图像完成转换并保存重载
- **THEN** 图像业务像素 SHALL 在原有编码精度内保留，包括完全透明区域的 RGB

### Requirement: Conversion uses source color content directly

转换材质 SHALL 使用源图内容与分辨率。Depth / Relief 和 Panorama Job SHALL 仅输出各自所需的几何数据产物；转换 SHALL 无需产生额外颜色文件。

#### Scenario: Depth or relief result is applied

- **WHEN** Job 返回深度、法线和 metadata
- **THEN** 转换 SHALL 使用原图或其独立副本完成材质绑定

#### Scenario: Panorama result is applied

- **WHEN** Job 返回深度和 metadata
- **THEN** 转换 SHALL 使用源全景颜色完成材质绑定

#### Scenario: Plane converts an animated image

- **WHEN** Plane 转换 movie 或 sequence 图像
- **THEN** 材质 SHALL 保留源 Empty 的帧起点、偏移、时长和循环设置

### Requirement: Conversion preserves source state on failure and undo

转换 SHALL 在失败时恢复复用原图的有效配置和像素，释放本次创建的临时资源，并保留源 Empty。成功转换 SHALL 支持 Undo / Redo。

#### Scenario: Material or object creation fails

- **WHEN** 原图已配置但转换在完成对象替换前失败
- **THEN** 原图的颜色空间、Alpha、业务像素和源 Empty 引用 SHALL 恢复
- **AND** 本次创建的未使用资源 SHALL 清理

#### Scenario: The source changes during an asynchronous job

- **WHEN** 结果应用时源对象失效或其 Image 已替换
- **THEN** 转换 SHALL 取消应用并保留当前源状态

#### Scenario: A completed conversion is undone and redone

- **WHEN** 用户撤销成功的转换再重做
- **THEN** 撤销 SHALL 恢复源 Empty 和转换前图像状态，重做 SHALL 恢复转换对象及对应材质配置

