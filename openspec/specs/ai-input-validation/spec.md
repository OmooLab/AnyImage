# ai-input-validation Specification

## Purpose
TBD - created by archiving change unify-ai-input-validation. Update Purpose after archive.
## Requirements
### Requirement: Shared input format validation

AI 输入 SHALL 使用公共格式规则，在 Blender 提交前与后端处理前校验实际输入路径。支持图片为 JPG/JPEG/PNG/WEBP，视频沿用当前 MP4/MOV/AVI/MKV/WEBM/M4V/MTS/MPG/MPEG，扩展名匹配忽略大小写。

#### Scenario: Unsupported file in image edits
- **WHEN** Remove BG 与 Upscale 使用同一个存在的 `.tiff` 普通文件，且环境和模型已就绪
- **THEN** 两者在提交 Job 前取消，展示相同格式提示，包含 `.tiff` 和分类排序的支持格式

#### Scenario: Direct backend input
- **WHEN** 后端直接收到不支持格式的文件或无扩展名文件
- **THEN** 使用与前端相同的格式提示规则，无扩展名显示 `(no extension)`

#### Scenario: Supported uppercase extension
- **WHEN** 实际输入为存在的 `.PNG` 或 `.MP4` 文件
- **THEN** 通过对应图片或视频格式校验

#### Scenario: Model image validation
- **WHEN** BEN2 单帧入口收到不支持的图片扩展名
- **THEN** 使用公共格式提示的图片子集，并与公共图片支持集合一致

### Requirement: Distinct input failure reasons

系统 SHALL 区分缺失路径、不支持格式、目录无有效帧和解码失败；提示 SHALL 适用于 Image Empty 和 Image Texture，解码异常转换 SHALL 限定于读取边界。

#### Scenario: Missing source file
- **WHEN** Image Empty 或材质 Image Texture 的源图片或视频文件不存在
- **THEN** 提示缺失的 source image/video file 及路径，不将原因报告为格式不支持

#### Scenario: Invalid encoded data
- **WHEN** 支持扩展名的文件内容无法作为对应图片或视频解码
- **THEN** 报告无法读取的媒体类型及路径，并保留底层异常供诊断

### Requirement: Explicit frame selection

系统 SHALL 在复制 Blender 序列前校验图片格式；通用目录 SHALL 仅收集支持的图片，保持现有排序及帧范围规则。

#### Scenario: Unsupported Blender sequence
- **WHEN** Blender 源序列使用 `.exr` 扩展名
- **THEN** 复制前提示不支持的图片格式，不创建临时帧目录

#### Scenario: Mixed directory
- **WHEN** 通用输入目录包含 JPG、PNG、TXT 和 EXR 文件
- **THEN** 仅 JPG 与 PNG 参与处理，前后端按相同规则选择并保持原帧范围语义

#### Scenario: Empty supported frame set
- **WHEN** 通用目录为空或只有不支持的文件
- **THEN** 提示无支持的图片帧、目录路径及支持的图片格式

### Requirement: Validate prepared media

系统 SHALL 校验实际提交的文件，保持各功能自身的媒体类型、尺寸和比例约束。

#### Scenario: Packed image exported as PNG
- **WHEN** 一个名称带 `.exr` 的 packed Image 经现有流程成功导出 PNG
- **THEN** 按导出的 PNG 校验，不按源名称拒绝

#### Scenario: Feature restriction
- **WHEN** 输入通过公共格式校验但不满足 Depth Plane 的静态图限制或 Upscale 的尺寸限制
- **THEN** 仍按对应业务原因取消，不报告为格式不支持

