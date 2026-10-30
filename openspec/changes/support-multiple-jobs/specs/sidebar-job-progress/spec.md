## ADDED Requirements

### Requirement: Compact job progress
`runtime.draw_jobs(layout)` SHALL 在开发者指定的任意布局中按提交顺序绘制每个未结束 Job，一行仅含横向进度条及文字和取消按钮。Runtime SHALL 自动在状态栏显示第一个正在运行的 Job，复用相同的进度、译文与定向取消。

#### Scenario: Status bar follows the first running job
- **WHEN** 多个任务已提交且至少一个正在运行
- **THEN** 状态栏仅显示按提交顺序找到的第一个运行任务；该任务结束后切换到下一个运行任务，没有运行任务时不显示任务行

#### Scenario: Developer chooses the list location
- **WHEN** 开发者在任意编辑器的 Panel 或其他布局中调用 `runtime.draw_jobs(layout)`
- **THEN** 完整任务列表在该布局显示和刷新，状态栏独立保持可见

#### Scenario: Running and queued jobs
- **WHEN** A 正在执行，B 排队
- **THEN** A 显示翻译后的进度，B 显示零进度和“等待中”，每行仅有自身取消按钮

#### Scenario: Terminal job disappears
- **WHEN** Job 成功、失败或取消
- **THEN** 终态处理后移除对应行，失败通过所属 Operator 报告，其他行继续显示

#### Scenario: Sidebar is closed
- **WHEN** 用户关闭侧边栏
- **THEN** 任务继续执行，状态栏仍显示首个运行任务，重新打开时列表反映当前任务状态

### Requirement: Cancellation targets the displayed job
取消按钮 SHALL 携带 Job ID，仅作用于对应任务，等待取消确认期间 SHALL 显示取消状态。

#### Scenario: Cancel a specific row
- **WHEN** 用户点击第二行的取消按钮
- **THEN** 仅第二行对应任务收到取消请求，其他任务进度保持独立
