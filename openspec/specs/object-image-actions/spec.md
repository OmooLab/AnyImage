# object-image-actions Specification

## Purpose
TBD - created by archiving change add-object-image-actions. Update Purpose after archive.
## Requirements

### Requirement: AnyImage mesh objects use one capability marker
系统 SHALL 为新创建的 Plane、Depth Plane、Relief Plane、Panorama 与全部 Cutout Mesh 写入布尔自定义属性 `o_image_object = True`。系统 MUST NOT 再写入或读取 `anyimage_mesh_shape`，也 MUST NOT 提供旧标记兼容路径。

#### Scenario: An AnyImage mesh object is created
- **WHEN** 任一 AnyImage 图片转换或 Cutout 流程成功创建 Mesh 对象
- **THEN** 结果对象包含值为真的 `o_image_object`，且不包含 `anyimage_mesh_shape`

#### Scenario: A regular mesh exists
- **WHEN** Mesh 不是由 AnyImage 图片流程创建
- **THEN** 系统不自动为其添加 `o_image_object`

#### Scenario: A legacy object is loaded
- **WHEN** 旧对象只有 `anyimage_mesh_shape` 而没有 `o_image_object`
- **THEN** 系统不将旧属性视为图片对象标记，也不自动迁移该对象

### Requirement: Marked objects expose existing image actions
系统 SHALL 在 3D View 与 Outliner 中为活动 Mesh 且 `o_image_object` 为真的对象显示 `AnyImage` 右键菜单。菜单 SHALL 提供 Remove Background、Upscale 和现有 AI 设置入口，并 MUST NOT 在本阶段显示 Delight。

#### Scenario: A marked image object is active
- **WHEN** 用户在 3D View 或 Outliner 右键带有 `o_image_object` 的 Mesh
- **THEN** `AnyImage` 菜单显示 Remove Background 和 Upscale

#### Scenario: An unmarked mesh is active
- **WHEN** 活动 Mesh 没有值为真的 `o_image_object`
- **THEN** 系统不显示对象图片操作菜单

#### Scenario: An Image Empty is active
- **WHEN** 用户右键 Image Empty
- **THEN** 系统继续显示既有 Image Empty 菜单，不将其作为 `o_image_object` Mesh 处理

### Requirement: Object actions resolve one explicit Color target
系统 SHALL 从标记对象的活动材质槽沿已知 AnyImage 材质连接解析唯一 Color Image Texture。无法解析、存在歧义或 Image 不可编辑时，对象图片操作 MUST NOT 执行，且 MUST NOT 回退到 Image Empty 或 Shader Editor 的活动节点。

#### Scenario: The generated material is intact
- **WHEN** 标记对象保留 AnyImage 创建的普通、Depth/Relief 或 Panorama 材质连接
- **THEN** Remove Background 与 Upscale 以其 Color Image Texture 为目标

#### Scenario: The material topology is unknown
- **WHEN** 材质被替换或修改，导致 Color Image Texture 无法唯一解析
- **THEN** 两项对象操作不可执行，且不处理其他上下文中的图片

#### Scenario: The target changes during processing
- **WHEN** 异步任务期间对象、材质槽、Material、Color 节点或 Image 绑定发生变化
- **THEN** 系统拒绝提交结果、清理临时资源并保持当前场景状态

### Requirement: Object actions isolate their result
系统 SHALL 在对象操作成功后只改变发起对象的 Color 显示结果，并保留对象几何、Modifier、其他材质节点和 `o_image_object`。Image 独占时 SHALL 保留其身份并更新内容；Image 或 Material 被其他目标共享时 SHALL 隔离发起对象所需的数据后再提交。

#### Scenario: The Color image and Material are exclusive
- **WHEN** 发起对象独占 Material，且 Color Image 没有其他实际用户
- **THEN** 系统保留 Image 身份并以处理结果更新其内容

#### Scenario: The Color image is shared by another node
- **WHEN** 其他节点或 Image Empty 仍引用同一 Color Image
- **THEN** 发起对象的 Color 节点使用独立结果，其他用户继续使用原图

#### Scenario: The Material is shared by another object
- **WHEN** 另一对象使用发起对象的同一 Material
- **THEN** 系统为发起对象隔离当前材质槽并提交结果，另一对象继续使用原 Material 与原 Color

#### Scenario: The user undoes an object action
- **WHEN** 用户撤销一次成功的对象 Remove Background 或 Upscale
- **THEN** 对象材质槽、Color Image 内容或绑定恢复到操作前状态

### Requirement: Marked objects expose color reference actions
系统 SHALL 在带有 `o_image_object` 的活动 Mesh 可唯一解析 Color Image Texture 时，在其 `AnyImage` 菜单提供 `Match Color Reference`。菜单 MUST NOT 提供 `Set Color Reference`；匹配 SHALL 使用该 Color Image 作为当前目标，并使用当前 Scene 在 `Color Match` Panel 中选择的参考，不得处理其他编辑器或对象中的图片。

#### Scenario: A marked object's Color image is valid
- **WHEN** 用户打开有效 AnyImage Mesh 的右键菜单
- **THEN** 菜单不显示 `Set Color Reference`，并在当前 Scene 存在另一有效参考时启用 `Match Color Reference`

#### Scenario: The object Color source is ambiguous
- **WHEN** 活动 Mesh 的材质连接无法唯一解析 Color Image Texture
- **THEN** `Match Color Reference` 不可执行，且不回退到 Image Empty 或 Shader Editor 活动节点

#### Scenario: An object match isolates shared material data
- **WHEN** 匹配目标的 Color Image 或 Material 仍被其他对象或节点共享
- **THEN** 系统仅隔离并修改发起对象所需的数据，其他用户继续显示原图

### Requirement: Baked objects relinquish the image capability
系统 SHALL 在 Bake 成功后移除结果对象的 `o_image_object`，使其按普通 Mesh 参与对象目标识别。3D View 和 Outliner SHALL 依照同一标记确定 AnyImage 对象右键菜单的可用性。

#### Scenario: Bake succeeds
- **WHEN** 支持的 AnyImage 对象成功 Bake
- **THEN** 结果对象没有 `o_image_object`，对象右键菜单与对象图片 Operator 的目标识别均不可用

#### Scenario: Bake is undone and redone
- **WHEN** 用户对成功 Bake 执行 Undo 后再 Redo
- **THEN** Undo 恢复原节点栈、能力标记和对象图片操作，Redo 恢复普通 Mesh 身份

#### Scenario: Bake fails
- **WHEN** Bake 处理失败
- **THEN** 源对象仍保留原能力标记及对象图片操作行为

#### Scenario: A baked material image texture is active
- **WHEN** 用户在 Shader Editor 中选择 baked 材质的有效 Image Texture 节点
- **THEN** 贴图节点的 AnyImage 菜单和图片操作沿用现有节点上下文逻辑，与对象标记独立
