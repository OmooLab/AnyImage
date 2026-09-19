# image-edit-results Specification

## Purpose
TBD - created by archiving change fix-cutout-density-and-image-edit-names. Update Purpose after archive.
## Requirements
### Requirement: Direct image edits preserve the complete source name
Remove Background、Upscale、Crop Box、Crop Lasso、Crop Polyline 和 Crop Perspective SHALL 使用源 Image 数据块的完整名称请求结果 Image 名称，包括名称中的 `.png` 等格式文字，并 SHALL NOT 主动添加材质贴图后缀。

#### Scenario: Remove Background edits a shared image
- **WHEN** Remove Background 编辑一个仍被其他对象引用的 Image
- **THEN** 新结果以源 Image 的完整名称请求命名，唯一性数字后缀仅由 Blender 自动追加

#### Scenario: Upscale edits a shared image
- **WHEN** Upscale 编辑一个仍被其他对象引用的 Image
- **THEN** 新结果保留源 Image 的完整名称且不添加 `_color`

#### Scenario: Selection Crop edits a shared image
- **WHEN** 任一 Selection Crop 路径编辑一个仍被其他对象引用的 Image，无论是否启用 Refine Selection 或 Keep Original
- **THEN** 新结果保留源 Image 的完整名称且不移除名称中的格式文字

#### Scenario: Perspective Crop edits a shared image
- **WHEN** Crop Perspective 编辑一个仍被其他对象引用的 Image，无论是否启用 Keep Original
- **THEN** 新结果保留源 Image 的完整名称且不移除名称中的格式文字

### Requirement: Image replacement follows Blender data-block identity
系统 SHALL 在源 Image 只由被编辑对象使用时以结果替换并清理旧数据，使结果最终恢复源 Image 的准确名称；源 Image 仍被共享或被 Keep Original 保留时，系统 SHALL 保留源数据并接受 Blender 自动生成的数字唯一性后缀。

#### Scenario: Unshared source is replaced
- **WHEN** 直接图片编辑替换一个没有其他用户且没有 Fake User 的源 Image
- **THEN** 旧 Image 被清理且结果 Image 最终使用源 Image 的准确名称

#### Scenario: Shared source is split
- **WHEN** 直接图片编辑替换一个仍有其他用户的源 Image
- **THEN** 其他用户继续引用源 Image，被编辑对象引用新结果，两个数据块的重名冲突由 Blender 自动解决

### Requirement: Material texture naming remains separate
系统 SHALL 仅对 Plane、Depth Plane、Cutout Shape 等生成材质贴图的工作流使用 `_color.png`、`_depth.exr`、`_normal.png` 等业务后缀，直接图片编辑 SHALL NOT 复用这些派生贴图名称。

#### Scenario: Plane conversion creates material textures
- **WHEN** 图片被转换为需要材质贴图的 Plane 或 Cutout 结果
- **THEN** 其 Color、Depth 和 Normal 数据继续按对应材质贴图规则命名

