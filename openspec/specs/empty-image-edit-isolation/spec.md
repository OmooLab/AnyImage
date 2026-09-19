# empty-image-edit-isolation Specification

## Purpose
TBD - created by archiving change isolate-shared-empty-image-edits. Update Purpose after archive.
## Requirements
### Requirement: Sharing is determined by other image Empty objects
系统 SHALL 在编辑结果提交时，以整个文件中是否存在其他保留的 Empty Image 引用同一源 Image 判断共享，覆盖隐藏物体及其他场景中的物体。判断 SHALL 使用物体与数据块身份，且 SHALL NOT 使用总引用数、Fake User 或界面计数显示作为分离依据。

#### Scenario: A hidden object shares the source
- **WHEN** 当前物体与一个隐藏的 Empty Image 引用同一 Image，且界面没有显示引用数量
- **THEN** 系统识别为共享图片

#### Scenario: An object in another scene shares the source
- **WHEN** 另一场景中的独立 Empty Image 引用当前源 Image
- **THEN** 系统识别为共享图片

#### Scenario: One object is linked to multiple collections
- **WHEN** 仅当前 Empty 引用源 Image，且该物体链接到多个集合
- **THEN** 系统按单独使用处理

#### Scenario: Non-Empty references exist
- **WHEN** 仅当前 Empty Image 引用源图，源图另有 Fake User 或用户手动建立的材质引用
- **THEN** 系统按单独使用处理

#### Scenario: Sharing changes during a job
- **WHEN** Job 提交后、结果应用前，另一个 Empty Image 开始引用源图
- **THEN** 最终提交按共享图片处理

### Requirement: Shared edits update only the current Empty
存在其他保留的 Empty Image 共用源图时，系统 SHALL 仅将当前物体绑定到独立编辑结果，并保持其他 Empty 的 Image 绑定、原图内容和显示状态。结果 SHALL 请求源 Image 的完整名称，由 Blender 处理唯一性后缀。

#### Scenario: Two Empty objects share one image
- **WHEN** A 与 B 共用同一 Image，用户编辑 A
- **THEN** A 使用编辑后的独立 Image，B 仍引用原 Image，原图像素、Packed 内容、名称及 B 的显示和动画设置保持原样

### Requirement: A sole image Empty retains its Image identity
没有其他保留的 Empty Image 共用源图时，系统 SHALL 将编辑结果提交到源 Image，保留数据块身份、完整名称与 Fake User 设置，且成功后 SHALL 释放本次临时结果数据。用户手动建立的其他引用 SHALL 保持原绑定。

#### Scenario: A sole Empty is edited
- **WHEN** 唯一使用源图的 Empty 完成图片编辑
- **THEN** 其 Image 身份和完整名称保持不变，内容及尺寸更新为结果，保存重开后内容正确，且不保留额外结果 Image

#### Scenario: A user manually references the source in a material
- **WHEN** 唯一 Empty 的源图另被用户手动用于材质
- **THEN** 编辑按单独使用提交，材质引用仍绑定同一 Image

#### Scenario: An animated job result is committed
- **WHEN** 单独使用的 Empty 收到动画图片编辑结果
- **THEN** 源 Image 身份和名称保持不变，帧来源及打包结果更新正确，物体动画播放设置按现有工具语义配置

### Requirement: Frame considers surviving Empty objects
Frame SHALL 按成功合并后仍保留的 Empty Image 判断活动源图是否共享，并在结果提交成功后执行合并源物体删除。

#### Scenario: All other sharing objects are merged
- **WHEN** A 与 B 共用源图，Frame 将 B 合并到活动物体 A，且没有其他 Empty 使用源图
- **THEN** A 的源 Image 原位更新，B 按合并规则删除

#### Scenario: A sharing object survives outside the merge
- **WHEN** Frame 将 B 合并到 A，合并之外的 C 仍引用 A 的源图
- **THEN** A 使用独立结果，C 及其源 Image 保持原样

### Requirement: Failed or cancelled edits preserve source state
统一提交入口 SHALL 覆盖本地编辑与 Job 图片编辑。取消或提交失败时，系统 SHALL 保留或恢复源 Image 内容与身份、物体绑定、显示及动画设置，并释放本次临时资源。

#### Scenario: Sole-image commit fails
- **WHEN** 原位提交在写入内容或配置显示期间失败
- **THEN** 源图内容、尺寸、Packed 数据及物体状态恢复到提交前状态，临时结果被清理

#### Scenario: Shared-image commit fails
- **WHEN** 共用图片的当前 Empty 提交失败
- **THEN** 当前物体恢复原绑定，其他 Empty 及原图保持原样，临时结果被清理

#### Scenario: An edit is cancelled
- **WHEN** 用户预览编辑后取消
- **THEN** 原图和所有 Empty 的绑定及显示状态保持原样

