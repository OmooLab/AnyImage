## Context

`ImageGesture` 已在屏幕空间维护 Polyline 的已提交顶点与移动光标，并在三个顶点后允许点击起点 8 px 范围完成。当前闭合圈只在进入命中范围后以固定尺寸出现，缺少接近过程反馈；Modal 也不处理 `DOUBLE_CLICK`。Mask 使用单一 WorkspaceTool 承载 Lasso、Brush 与 Polyline，当前未声明工具光标。

Blender 的 Polyline Gesture 将实际点击半径与更大的视觉提示范围分开：实际命中半径为 `15 × UI Scale`，鼠标进入约为该半径平方的提示距离后，起点圈从 `1 × UI Scale` 平滑放大到实际命中半径。Polyline modal keymap 将左键双击作为 Confirm；Sculpt 的 Box、Lasso、Line 与 Polyline Mask/Hide 工具统一使用 `PAINT_CROSS`。

## Goals / Non-Goals

**Goals:**

- 让 Polyline 起点闭合提示具有与 Blender 一致的渐进接近反馈和命中范围。
- 支持双击完成有效 Polyline，并保留现有完成、回退和取消方式。
- 让统一 Mask Tool 使用适合区域编辑的十字光标。
- 将距离、缩放与事件判定保持为易单测的屏幕空间逻辑。

**Non-Goals:**

- 不调用或包装 Blender 内建 Polyline Operator。
- 不改变 Polyline 顶点投影、Selection 栅格化或 Alpha 合成。
- 不加入起点吸附、自动修改最后一个顶点或新的用户设置。
- 不拆分现有单一 Mask Tool。

## Decisions

### 1. 分离闭合命中半径与视觉提示距离

定义 15 px 基础闭合半径，并使用操作开始时读取的 UI Scale 得到实际命中半径。视觉提示距离沿用 Blender 的 `scaled_radius²`；只有已提交至少三个点且鼠标位于该范围内时才绘制起点圈。

提示圈半径使用 smoothstep 随距离插值：鼠标位于提示范围边缘时接近 `1 × UI Scale`，位于起点时等于实际闭合半径。绘制使用一明一暗的相邻轮廓，使提示在亮、暗图片上都可辨认。

选择独立的纯计算 Helper，而不是在 Draw Handler 内直接散落公式，以便精确测试边界、单调性和 UI Scale。

### 2. 点击只使用实际闭合半径

渐进提示范围只控制视觉反馈，不扩大可点击区域。普通左键按下仍先判断是否已有三个点且光标位于实际闭合半径内；命中时直接完成并且不提交新顶点，否则沿用现有最小点距规则添加顶点。

不使用整个提示范围作为命中范围，避免鼠标离起点较远时意外闭合。

### 3. Modal 同时处理原生双击与连续按下

`ImageGesture._modal_polyline()` 在普通左键按下分支之前处理 `LEFTMOUSE` 的 `DOUBLE_CLICK`。同时记录最近一次左键按下的位置与时间：当 Blender 只向 Python Modal 连续发送两个 `PRESS` 时，使用用户设置中的双击间隔和 `5 px × UI Scale` 位移范围识别第二击。当已提交至少三个点时复用 `_confirm_polyline()`；点数不足时保持 Modal，不应用 Selection。

Blender 内建 Gesture 依靠 Modal Keymap 将双击转换为 Confirm，但当前 Python Operator 没有该映射，因此不能只依赖 `DOUBLE_CLICK` 事件。不为 WorkspaceTool 增加第二个启动 keymap 项，因为双击发生时 Operator 已处于 Modal，连续按下判定可以避免再次启动 Operator 或复制完成逻辑。双击只完成现有已提交路径，第二击不得添加重复顶点。

### 4. 统一 Mask Tool 使用 PAINT_CROSS

在 `MaskTool` 上声明 `bl_cursor = "PAINT_CROSS"`。这会覆盖 Lasso、Brush 与 Polyline，符合 Blender 对 Sculpt Mask/Hide 区域手势的统一光标约定，也避免根据 Gesture 动态设置和恢复 Window cursor。

### 5. 保留当前项目已有控制

Enter、Numpad Enter、Backspace、RMB、Esc、工具切换取消和至少三个已提交点的完成门槛保持不变。状态文本补充双击完成，但不改变 Mode 或 Brush Radius 的展示。

## Risks / Trade-offs

- [提示距离按半径平方后明显大于实际命中范围] → 圆圈在远处保持接近 1 px，并通过连续放大表达接近程度；点击仍严格限制在实际半径内。
- [UI Scale 与 Region 坐标可能在不同平台产生取整差异] → 全程使用浮点屏幕坐标，只在比较和绘制中复用同一个缩放值，并对 1.0 与非 1.0 Scale 建立单测。
- [Python Modal 可能收到原生 `DOUBLE_CLICK`，也可能只收到连续 `PRESS`] → 同时支持两种事件链；连续按下仅在用户双击时间和小范围位移内成立，第二击不追加点。
- [`PAINT_CROSS` 同时影响非 Polyline Gesture] → Blender 的 Box、Lasso 与 Polyline Mask/Hide 本身采用同一光标，因此统一行为优先于引入动态 cursor 生命周期。

## Migration Plan

先替换闭合提示计算与绘制，再加入双击事件和 Tool cursor，随后更新状态文本、测试与内部文档。此变更不迁移持久数据；回滚只需恢复旧的固定半径提示、事件分支与默认 cursor。

## Open Questions

无。交互常量、光标范围和双击完成语义均以 Blender 当前 Polyline Gesture 为准。
