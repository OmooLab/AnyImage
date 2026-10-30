## Why

BlendJob 后端已有顺序执行队列，但 Blender 侧的单个 `active_job` 阻止连续提交。AnyImage 需要允许用户连续触发多个去背景等任务，并在侧边栏清楚地查看和取消各任务。

## What Changes

- Runtime 管理多个独立 Job；复用后端 FIFO 队列，每个 Job 独立持有输入、进度、结果、取消和清理生命周期。
- **BREAKING**：`JobOperatorBase` 更名为 `JobOperator`，移除旧导出和兼容入口；Operator 绑定自己的 Job。
- **BREAKING**：删除 `is_busy()`，执行资格统一通过 `can_submit()`；允许 `OFFLINE`、`STARTING`、`IDLE`、`PROCESSING` 提交，其他状态拒绝。
- 状态栏自动显示第一个正在运行的任务；开发者在任意布局调用 `runtime.draw_jobs(layout)`，每个未结束 Job 仅一行 `[进度条与译文] [×]`。
- 单行取消仅作用于对应 Job；停止、重启、迁移及卸载插件负责整个队列的终止和清理。
- AnyImage 连续提交时保存各自的目标、参数与输入，结果写回各自目标。安装及模型准备入口保持独立。
- 同步开发文档、相关测试和本地 BlendJob 依赖。

## Capabilities

### New Capabilities
- `multiple-job-runtime`：多 Job 提交、FIFO 生命周期、状态及取消维护。
- `sidebar-job-progress`：侧边栏精简进度列表与按 Job 取消。
- `queued-image-jobs`：AnyImage 连续提交时的输入与目标隔离。

### Modified Capabilities
- `server-lifecycle-controls`：使用现有统一状态命名，启停及重启协调全部任务。

## Impact

- `D:/Projects/BlendJob`：Runtime、Operator、控制进程、取消协议、翻译、导出、文档与测试。
- AnyImage：所有 JobOperator 子类、AI 操作入口、任务输入与结果绑定、侧边栏、相关测试和 Runtime 文档。
- `pyproject.toml`、`uv.lock`、本地 wheel 与 Manifest 的依赖一致性检查。
