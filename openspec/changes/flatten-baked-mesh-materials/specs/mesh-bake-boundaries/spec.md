## MODIFIED Requirements

### Requirement: Bake validates the operations performed
系统 SHALL 根据纯几何固化、多区 Color 拼接、Roughness 与最终 Normal 烘焙所执行的操作分别验证输入。图片可写性 SHALL 仅用于需要改写的图片；采样和 UV 限制 SHALL 对应实际重采样或烘焙的假设。

#### Scenario: Single-region geometry has no normal image
- **WHEN** Bake 固化单区几何使用 Shadeless 且无需改写 Color 或烘焙任何材质输出
- **THEN** 系统保留 Color 图片及节点采样设置，允许与几何固化无关的动画图片来源和 Closest 插值

#### Scenario: Color tiles are materialized
- **WHEN** Bake 根据来源区域拼接并更新 Color 图片
- **THEN** 系统在提交前验证来源区域、UV、图片写入和采样所需条件

#### Scenario: Normal is baked
- **WHEN** Bake 将现有 Normal 固化到最终 UV
- **THEN** 系统验证法线与 Bump 连接、烘焙坐标和采样条件；已有目标图片验证可写性，仅有 Bump 时允许新建独立 Normal 目的地

#### Scenario: Roughness requires shader evaluation
- **WHEN** 单区或多区材质需要固化 Roughness
- **THEN** 系统按实际采样验证来源图片及 UV，提交前拒绝无法静态求值的输入


### Requirement: Bake preserves the texture transaction
系统 SHALL 继续原位处理支持的对象，保持对象身份、变换、集合、无共享时的既有材质与图片身份、图片名称和路径及用户数据。失败 SHALL 恢复原数据与对象能力，并释放临时资源。成功 SHALL 支持 Undo/Redo。

#### Scenario: Bake fails after partial image updates
- **WHEN** Bake 在部分图片写入后失败
- **THEN** 原图片、材质节点及连线、Mesh、Modifier 和对象能力标记恢复，临时资源释放

#### Scenario: Shared material and images are baked
- **WHEN** Bake 的材质或图片有其他使用者
- **THEN** 系统隔离共享资源，其他使用者保留原节点组及原图片内容

### Requirement: Bake follows existing reference candidate categories
系统 SHALL 保留现有 `_color`、`_normal`、`_depth`、`_roughness` 图片名称及参考候选过滤。Bake 贴图更新 SHALL 沿用专属写入事务，参考缓存刷新 SHALL 由允许的参考图片编辑流程负责。

#### Scenario: Baked textures exist
- **WHEN** 带生成贴图类别后缀的图片完成 Bake，包含扩展名和 Blender 数字重名后缀
- **THEN** 这些图片仍不出现在 Color Reference 候选中
