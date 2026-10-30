## ADDED Requirements

### Requirement: Repeated image job submission
AnyImage SHALL 用 `can_submit()` 判断任务执行资格，使用 `JobOperator` 连续提交多个图像任务，并独立保存每次提交的目标、参数和输入。

#### Scenario: Remove backgrounds from different images
- **WHEN** 对 A 提交去背景后切换到 B 并再次提交
- **THEN** 两个任务均被接受，结果分别应用到 A 和 B，临时输入相互独立

#### Scenario: Repeat on the same image
- **WHEN** 同一图像在首个结果返回前再次提交
- **THEN** 每个任务使用各自提交时的输入，成功结果按提交顺序应用

#### Scenario: Target disappears
- **WHEN** 排队任务的目标被删除或已不能安全应用结果
- **THEN** 该任务报告失败并清理，不修改当前选中的其他图像，也不阻断后续任务

### Requirement: Sidebar integration and setup entry
AnyImage SHALL 在侧边栏使用 `runtime.draw_jobs(layout)` 绘制任务，安装与模型准备保持独立入口。

#### Scenario: Environment missing
- **WHEN** Runtime 为 UNAVAILABLE
- **THEN** 生成任务不可提交，安装入口可用
