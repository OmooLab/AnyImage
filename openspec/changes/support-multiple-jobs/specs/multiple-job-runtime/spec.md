## ADDED Requirements

### Requirement: Independent queued jobs
Runtime SHALL 接受多个 Job，复用 FIFO 串行队列，并由每个 Job 独立持有 controller、Operator、进度、结果及清理生命周期。

#### Scenario: Submit while processing
- **WHEN** A 正在运行时提交 B 和 C
- **THEN** 三个 Job 均被接受，按 A、B、C 执行，各自结果仅交给所属 Operator

#### Scenario: Callback failure
- **WHEN** A 的 response 抛出异常
- **THEN** A 报告失败并恰好清理一次，B 和 C 仍能继续执行

### Requirement: Submission eligibility and operator API
系统 SHALL 使用 `JobOperator`，保留 request、response、cleanup 职责，删除 `JobOperatorBase` 和 `is_busy()`。`can_submit()` SHALL 仅在 OFFLINE、STARTING、IDLE、PROCESSING 为真。

#### Scenario: Cold start accepts a queue
- **WHEN** 首次任务触发启动，服务器仍处于 STARTING
- **THEN** 后续提交被接受并排队，启动失败时受影响任务终结并清理

#### Scenario: Maintenance rejects submission
- **WHEN** 状态为 UNAVAILABLE、INSTALLING、MIGRATING、STOPPING 或 ERROR
- **THEN** `can_submit()` 返回假，实际提交入口也拒绝创建新执行任务

### Requirement: Cancellation and maintenance cover all jobs
系统 SHALL 按 Job ID 取消单个任务，维护操作 SHALL 阻止新提交、取消全部任务、等待终态与清理后继续。取消请求与成功竞争时 SHALL 不应用已取消任务的结果。

#### Scenario: Cancel one queued job
- **WHEN** A 执行中、B 和 C 排队时取消 B
- **THEN** B 不执行且完成清理，A 和 C 保持正常生命周期

#### Scenario: Migrate a busy runtime
- **WHEN** 多个任务未结束时确认迁移
- **THEN** 全部任务被取消并清理，服务停止后才搬移目录，AnyImage 无需处理队列细节

#### Scenario: Control process exits
- **WHEN** 控制进程异常退出
- **THEN** 受影响任务均终结并清理，Runtime 为 ERROR，列表没有永久等待任务

#### Scenario: Single cancellation requires forced stop
- **WHEN** A 忽略取消且需要强制停止服务，而 B 仍在排队
- **THEN** A 终结并清理，B 能重新启动服务后继续执行；整队停止操作则同时取消 B
