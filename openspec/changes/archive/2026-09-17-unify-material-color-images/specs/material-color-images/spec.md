## Purpose

统一 Cutout、Convert To 与剪贴板 Plane 的材质颜色图来源和交付约定，使裁切与整图转换使用同一范围采样流程，并保障材质编辑、再次导入原文件及保存重载时图像内容与设置保持隔离。

## ADDED Requirements

### Requirement: Material color uses the requested source bounds

所有材质生成入口 SHALL 按本次准备时的源图像素和范围生成颜色图。Cutout SHALL 使用裁切范围，四种 Convert To 与剪贴板 Plane SHALL 使用整图范围。AI 的参与 SHALL 保持相同颜色来源及颜色分辨率。

#### Scenario: Cutout uses or omits AI

- **WHEN** 同一源图和裁切范围分别执行普通 Cutout 和需要 AI 的 Cutout
- **THEN** 两者的颜色图 SHALL 对应同一裁切内容、尺寸和原有 Alpha，包含透明区域 RGB

#### Scenario: A full image is converted

- **WHEN** 执行 Plane、Depth Plane、Relief Plane、Panorama 或剪贴板 Plane
- **THEN** 颜色图 SHALL 对应完整源图片，保持原始尺寸和当前像素

### Requirement: Every material owns an isolated color image

每次生成材质 SHALL 使用独立 Color Image 和独立临时颜色文件路径，以源图基名、`_color` 及实际文件后缀命名并打包。原 Image 的内容和解释设置 SHALL 保持不变，材质 Color SHALL 不携带剪贴板原图缓存身份。

#### Scenario: Source users vary

- **WHEN** 原图没有其他用户，或被其他 Empty、材质或笔刷引用
- **THEN** 新材质 SHALL 使用独立颜色图，原图的引用、像素、名称、路径、颜色空间及 Alpha 模式 SHALL 保持原值

#### Scenario: Original file is imported after material painting

- **WHEN** 转换后修改材质颜色图，再次按原文件路径导入图片，包括原 Image 已移除的情况
- **THEN** 导入 SHALL 不命中材质颜色图，不带入该颜色图的材质设置和绘制像素

### Requirement: Encoding preserves color precision and presentation

颜色图 SHALL 保留对应范围的 RGB、Alpha、透明区域 RGB 及源编码精度，float / HDR SHALL 保留浮点范围。普通 byte 材质 SHALL 沿用颜色空间适配与 Alpha 配对规则，所有 float / HDR 材质 SHALL 保留源颜色空间与 Alpha 模式。

#### Scenario: Ordinary material is configured

- **WHEN** 普通 byte 材质适配关闭或回退到 sRGB，或者启用可用的 inverse 空间
- **THEN** 颜色图 SHALL 分别采用 sRGB + PREMUL 或对应 inverse 空间 + STRAIGHT，原图设置保持不变

#### Scenario: HDR and unsaved pixels are serialized

- **WHEN** float / HDR、generated、dirty 或 packed 源图完成颜色图生成、打包和保存重载
- **THEN** 结果 SHALL 在对应编码精度内保留业务像素、动态范围与选定的颜色解释
- **AND** 所有 float / HDR 材质 SHALL 保留源图颜色空间与 Alpha 模式；Panorama 非 sRGB 分支沿用源解释

#### Scenario: Float source interpretation prevents lossless serialization

- **WHEN** 按源颜色空间和 Alpha 模式解码 EXR 后无法保留源浮点像素
- **THEN** 操作 SHALL 明确拒绝转换，清理临时资源并保持源图不变
- **AND** float / HDR 材质 SHALL 不启用场景视图适配的 Alpha Fix

### Requirement: Material operations release temporary resources safely

临时颜色文件 SHALL 在打包和相关 Job 使用结束后释放。取消或失败 SHALL 清理本次临时文件与未交付数据，保留源对象及原图。成功转换 SHALL 支持 Undo / Redo；异步源对象失效或 Image 被替换时 SHALL 取消应用。

#### Scenario: Packed result survives file cleanup

- **WHEN** 操作成功且临时目录已删除
- **THEN** 材质颜色图 SHALL 仍能正确读取并保存重载

#### Scenario: An operation fails or is cancelled

- **WHEN** 导出、模型处理、图像加载、材质或对象创建失败，或用户取消 Job
- **THEN** 本次临时资源 SHALL 释放，源对象、源像素和源图设置保持原值

#### Scenario: Conversion is undone and redone

- **WHEN** 用户撤销并重做转换
- **THEN** 撤销 SHALL 恢复源对象和源图，重做 SHALL 恢复带独立颜色图的转换结果

### Requirement: Plane accepts static images only

Convert to Plane SHALL 仅接受静态图片；Movie、Sequence 和动画图像 SHALL 在创建颜色图或对象前被拒绝，并给出明确错误。

#### Scenario: Animated source is selected

- **WHEN** 源 Image 为 Movie 或 Sequence，即使其声明时长为一帧，或源图片含多帧
- **THEN** Plane SHALL 报告仅支持静态图片，并保持源对象及图像不变
