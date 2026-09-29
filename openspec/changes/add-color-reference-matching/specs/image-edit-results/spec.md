## ADDED Requirements

### Requirement: Color matching follows direct image edit result rules
`Match Color Reference` SHALL 作为直接图片编辑保留源 Image 的完整名称和颜色解释设置。目标 Image 独占时 SHALL 保留其身份并更新内容；目标 Image 仍被共享时 SHALL 为当前目标提交独立结果，并由 Blender 处理名称唯一性。

#### Scenario: An unshared target is matched
- **WHEN** `Match Color Reference` 成功处理一个没有其他实际用户的目标 Image
- **THEN** 目标 Image 身份、完整名称与颜色解释设置保留，内容更新为匹配结果

#### Scenario: A shared target is matched
- **WHEN** 另一 Image Empty、纹理节点或对象仍使用目标 Image
- **THEN** 发起目标使用独立匹配结果，其他用户继续使用原 Image，结果不添加材质贴图后缀

#### Scenario: The reference is also used elsewhere
- **WHEN** 参考 Image 被多个对象或节点使用
- **THEN** 颜色匹配只读取参考像素，不修改其内容、名称、绑定或用户
