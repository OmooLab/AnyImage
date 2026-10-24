## ADDED Requirements

### Requirement: Marked objects expose color reference actions
系统 SHALL 在带有 `o_image_object` 的活动 Mesh 可唯一解析 Color Image Texture 时，在其 `AnyImage` 菜单提供 `Set Color Reference` 与 `Match Color Reference`。两项操作 SHALL 使用该 Color Image 作为当前图片，不得处理其他编辑器或对象中的图片。

#### Scenario: A marked object's Color image is valid
- **WHEN** 用户打开有效 AnyImage Mesh 的右键菜单
- **THEN** 菜单显示 `Set Color Reference`，并在当前 Scene 存在另一有效参考时启用 `Match Color Reference`

#### Scenario: The object Color source is ambiguous
- **WHEN** 活动 Mesh 的材质连接无法唯一解析 Color Image Texture
- **THEN** 两项颜色参考操作不可执行，且不回退到 Image Empty 或 Shader Editor 活动节点

#### Scenario: An object match isolates shared material data
- **WHEN** 匹配目标的 Color Image 或 Material 仍被其他对象或节点共享
- **THEN** 系统仅隔离并修改发起对象所需的数据，其他用户继续显示原图
