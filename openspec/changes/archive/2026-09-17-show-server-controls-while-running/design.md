## Context

`ServerPanel.draw()` 目前把 `READY` 与 `BUSY` 都显示为 Running，但只在 `READY` 分支创建重启和停止按钮。Cached 模型名称则通过逗号拼接到单个 Label，模型较多时会形成过长的一行。

BlendJob 当前以 `READY` 表示等待任务、以 `BUSY` 表示执行任务；二者都是 Server 已运行的子状态。此次调整只改变 Blender 面板布局，不改变状态协议或生命周期 Operator。

## Goals / Non-Goals

**Goals:**

- 统一 Running 判定，使所有运行中子状态共享重启和停止按钮。
- 保留各子状态原有的状态文本和图标。
- Cached 包含多个模型时，将模型名称逐项分行显示。
- 用 UI 测试锁定状态与布局行为。

**Non-Goals:**

- 不改变 Server 启动、重启、停止或任务取消语义。
- 不新增 Server 状态、API 或依赖。
- 不改变模型缓存的内容、顺序或清理行为。

## Decisions

### 统一复用 Running 判定

在读取 `server_status()` 后，以同一个 Running 判定驱动状态标签、生命周期按钮和 Cached 区域。当前 Running 状态集合为 `READY` 与 `BUSY`：`READY` 表示运行并等待，`BUSY` 表示运行并处理任务。

相比在 `READY` 与 `BUSY` 分支分别创建按钮，集中判定可避免后续运行中展示再次分叉。非 Running 状态继续沿用现有 Start 或状态提示分支。

### Cached 多项使用纵向列表

无缓存和单个缓存模型保留紧凑的一行展示；两个及以上缓存模型使用纵向布局，每个模型名称占一行，并保留同一区域的清理按钮。

相比在 Label 文本中插入换行，使用 Blender Layout 的独立 Label 能稳定参与面板布局，也便于测试每个模型项。

## Risks / Trade-offs

- [Busy 时停止或重启会中断当前任务] → 这是用户主动触发的既有生命周期行为；本变更只恢复入口，不改变 Operator 语义。
- [多个模型使面板变高] → 仅在确有多个缓存模型时展开，并以可读性优先。
- [状态分支与按钮分支再次偏离] → 使用同一个 Running 判定，并覆盖 `READY`、`BUSY` 与非 Running 状态测试。
