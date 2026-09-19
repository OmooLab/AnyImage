## Context

Cutout、Image Box 和 Image Lasso 都通过 View3D WorkSpaceTool 设置暴露 `Fit to Foreground`。共享绘制函数当前先绘制禁用的属性，再在末尾追加 AI 设置按钮；Cutout 还直接绘制 `Generate Normal Map`，并始终在 shape pie 中提供两个本地 shape 和两个 Depth shape。

AI 可用性已经由 `ai_status()` / `ai_ready()` 统一表示，包含运行环境和所需模型状态。实现应继续复用该状态，不引入第二套环境判定。

## Goals / Non-Goals

**Goals:**

- 三个工具在 AI 未就绪时都将 AI 设置入口放在工具设置开头。
- 所有依赖 AI 的属性在未就绪时不可编辑，且遗留值不会触发 AI job。
- Cutout shape pie 根据 AI 可用性展示两个或四个候选。
- 保持共享绘制和状态判定逻辑集中，便于 Image Box、Image Lasso 与 Cutout 复用。

**Non-Goals:**

- 不删除或重构四个 Cutout shape 及其节点资产。
- 不改变 AI 环境安装流程、模型目录、job 协议或生成算法。
- 不调整 Image Line 和 Image Polyline；它们没有 `Fit to Foreground` 设置。

## Decisions

### 复用单一 AI 状态绘制一组设置

在共享图像交互模块中拆出小型绘制函数：同一个 `ai_status()` 结果先决定是否绘制设置按钮，再决定相关属性行是否启用。Cutout 使用这些函数组合 `Fit to Foreground`、本地 mesh spacing 和 `Generate Normal Map`；Image Box 与 Image Lasso 继续通过共享区域设置入口绘制。

相比每个工具分别查询状态和创建按钮，这能保证按钮顺序、文案与禁用条件一致，也避免一次绘制中状态变化造成不一致。

### shape pie 在创建时按 AI 可用性过滤

`open_shape_pie` 在读取 Cutout 工具设置时查询一次 `ai_ready()`：未就绪时只创建 `Surface` 和 `Balloon` 按钮；就绪时再追加 `Depth Balloon` 和 `Depth Surface`。四个 shape 的定义、索引和执行支持保持不变。

相比禁用两个 Depth 按钮，直接隐藏能把无 AI 环境时的选择明确收敛为两个可执行结果，并符合用户期望的两项菜单。

### 在交互边界清除不可用的 AI 选项

传给 Cutout operator 的 `generate_normal` 必须同时满足设置为真和 `ai_ready()`。`Fit to Foreground` 继续通过共享 `apply_region_settings` 做相同门控。这样即使 `.blend` 文件或先前会话保留了真值，选择本地 shape 也不会弹出 AI 安装流程。

相比在 operator 执行阶段静默改写参数，在设置读取边界门控更直接，并使 pie 按钮携带的参数准确表达实际操作。

## Risks / Trade-offs

- [AI 状态查询可能涉及模型状态扫描] → 每个设置绘制或 shape pie 打开过程只查询一次并复用结果。
- [隐藏 Depth shape 后用户可能不知道完整能力] → 设置开头持续显示带有当前缺失状态文案的 AI 设置按钮。
- [旧文件保留已勾选的 AI 属性] → UI 置灰且交互参数显式与 `ai_ready()` 合取，不依赖用户手动清除。
