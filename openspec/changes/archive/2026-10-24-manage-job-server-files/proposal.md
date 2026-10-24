## Why

任务产物持续占用磁盘，需要集中在 Job Server 侧边栏提供维护入口。

## What Changes

- 增加带大小预览和确认的 Clear Job Files，保护进行中任务及未打包图片引用。
- 将 Open Server Log 移至 Job Server；Unload Models 显示完整文字并移除右键入口。

## Capabilities

### New Capabilities
- `job-file-maintenance`: 安全清理任务文件及对应内存历史。

### Modified Capabilities

## Impact

涉及服务端任务文件维护、Blender Operator、侧边栏、偏好设置与菜单测试。不修改模型或依赖。
