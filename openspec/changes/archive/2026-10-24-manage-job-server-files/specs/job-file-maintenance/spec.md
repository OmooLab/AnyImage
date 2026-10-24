## ADDED Requirements

### Requirement: Job files are cleared safely

系统 SHALL 在确认后清理所选历史任务目录并同步内存历史，保护活动任务、排队任务、尚未导入的结果、当前 Blender 未打包图片引用与目录边界。

#### Scenario: Idle cleanup
- **WHEN** 用户确认清理且服务端空闲
- **THEN** 仅删除确认范围内的安全任务目录，模型、环境与 server.log 保持不变

#### Scenario: Protected or unsafe content
- **WHEN** 任务正在使用、图片尚未打包或路径包含重解析点
- **THEN** 拒绝清理或跳过对应目录并反馈结果

### Requirement: Maintenance controls live in the server sidebar

系统 SHALL 在 Job Server 侧边栏提供带文字的 Unload Models、Clear Job Files 和 Open Server Log；右键菜单 SHALL 不再提供 Unload Models，偏好设置 SHALL 不再提供 Open Server Log。

#### Scenario: Draw maintenance controls
- **WHEN** 用户打开 Job Server 侧边栏
- **THEN** 可查看日志，并在安全状态下卸载模型或确认清理任务文件
