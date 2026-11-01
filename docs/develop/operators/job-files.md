# Job 文件清理

BlendJob 注册 `anyimage.clear_job_files` 和确认 Operator，`DangerZonePanel` 提供入口。Runtime 在服务空闲时预览可清理的 Job 目录，确认对话框显示任务数量和总大小。

确认时 Runtime 提交预览中的 Job 清单和服务实例标识，服务端核对后删除任务产物与日志，返回删除数量、大小和保留结果。
