## ADDED Requirements

### Requirement: Scene reference changes release only unused resources
系统 SHALL 按实际 Scene 与活动交互引用管理参考资源。一个 Scene 清空或替换参考 SHALL 保留其他 Scene 仍在使用的派生数据、图标和色板。

#### Scenario: Two scenes share one reference
- **WHEN** Scene A 与 B 使用同一参考，B 清空选择
- **THEN** A 的参考、预览图标、色板与匹配能力保持有效

#### Scenario: Scenes have different references
- **WHEN** Scene B 替换自己的参考
- **THEN** Scene A 的参考资源与显示保持有效，B 的旧资源在没有使用者时释放

### Requirement: Long-lived reference data has bounded pixel storage
系统 SHALL 将参考签名、色板和有界缩略图用于长期复用。完整像素快照 SHALL 仅在参考准备和活动交互校验期间保留，且在相应生命周期结束后释放。匹配开始和提交 SHALL 校验实际参考内容。

#### Scenario: Many large references are selected in sequence
- **WHEN** 用户连续选择多张大图，旧参考不再被 Scene 或活动交互使用
- **THEN** 旧参考全尺寸像素与预览资源被释放，长期缓存不累计完整 RGBA 快照

#### Scenario: Reference content changes during matching
- **WHEN** 参考实际像素在预览和确认之间变化
- **THEN** 操作识别变化并拒绝基于旧参考提交，释放本次交互快照

### Requirement: Reference restoration follows Blender data lifecycle
系统 SHALL 在 load、Undo、Redo 后根据各 Scene 的恢复数据重新同步参考、预览与派生色板，并在扩展注销时释放自身缓存、handler 和预览资源。

#### Scenario: Undo restores scene references
- **WHEN** Undo 或 Redo 恢复多个 Scene 的参考与图片内容
- **THEN** 各 Scene 的展示对应恢复后的图片，活动资源没有悬空的旧数据

#### Scenario: Reference components are registered repeatedly
- **WHEN** 扩展重复注册和逆序注销参考相关入口
- **THEN** handler 与预览资源数量有界，并在注销完成后释放
