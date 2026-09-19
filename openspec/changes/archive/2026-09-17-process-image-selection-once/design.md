## Context

当前 Viewport 手势已经能够把屏幕路径转换为 `SelectionPath`，却会立即把它编码到 `selection_path_json` Property；Image Tool 随即反解同一个值。Cutout 还会在打开 Shape Pie Menu 前读取整图并将路径栅格化为 `SelectionMask` 做可见性验证；用户选定 Shape 后，`CutoutSelectionToShape` 再次读取和栅格化。Image Tool 的实际编辑阶段也会因 helper 隐式读取图片而重复取得同一 RGBA。

本文将用户所说的“序列化选区”明确为昂贵的 `SelectionPath → SelectionMask` 构建过程。`SelectionPath.to_json()` 只是 Blender Operator Property 之间传递轻量路径值的编码，不需要额外状态或缓存。

## Goals / Non-Goals

**Goals:**

- Image Tool 与 Cutout Tool 复用同一条手势主链，只构建一次 `SelectionPath`。
- Image Tool 在同一 Operator 内直接传递 `SelectionPath`，不做 JSON 往返。
- Image Tool 只在图片编辑执行阶段构建一次 `SelectionMask`。
- Cutout 只在 `CutoutSelectionToShape` 执行阶段构建一次 `SelectionMask`。
- 同一执行阶段显式复用源图 RGBA 与 Selection Mask，避免 helper 隐式重读或重建。

**Non-Goals:**

- 不引入令牌、全局表、Window 临时状态或 Selection 缓存。
- 不修改 Selection Path 的 JSON 格式、填充规则、抗锯齿核、Alpha 阈值或最终边界语义。
- 不修改 Cutout 网格算法、Shape Pie Menu 布局或 AI Job 协议。
- 本次不把全尺寸 Selection Mask 改为局部画布实现。

## Decisions

### 1. 手势阶段只构建并传递 Selection Path

`ImageSelectionGesture` 继续负责屏幕坐标到图片坐标的转换，并构建一次 `SelectionPath`。完成边界把该 Python 值交给可覆盖的实际操作提交方法，不再统一写入 `selection_path_json`。Image Tool 与 Cutout Tool 都复用该结果，不在手势完成回调中读取图片像素或调用 Selection Mask 栅格化。

Image Tool 在同一个 Operator 实例中保存内存 Selection Path，并直接进入图片编辑执行方法，因此删除自身的 `selection_path_json` Property 和 JSON 编解码。Cutout Tool 把同一个 Python 值交给 Shape Pie Menu；由于按钮会启动新的 Operator，菜单只在这里把 Path 编码一次，并将同一个 JSON 字符串设置到各 `CutoutSelectionToShape` 的 `selection_path_json` Property。菜单层不解析、验证或构建 Selection Mask，也不需要令牌中转。

相比令牌或临时表，直接传递现有 Operator Property 没有生命周期、失效、跨 Window 或菜单取消清理问题，并且已经满足 Blender UI Operator 的可序列化参数约束。

### 2. Selection Path 到 Selection Mask 的步骤只存在于实际执行阶段

Image Tool 的实际编辑方法直接接收手势阶段构建的 Selection Path、读取一次源图 RGBA，并将 Path 栅格化为一次 Selection Mask，再进入本地编辑或 Refine Selection 输入准备。`execute` 不再通过隐藏 JSON Property 恢复同一 Operator 已经持有的路径。

`CutoutSelectionToShape.execute` 是 Cutout 的实际生成边界：它直接接收 Pie Menu 传来的 Selection Path 值，读取一次源图 RGBA，并将 Path 栅格化为一次 Selection Mask，再进入 Surface、Balloon 或 AI Shape 主链。

Cutout 菜单前的 `validate_cutout_selection` 整体删除。路径结构仍由 `SelectionPath` 构建时验证；必须读取像素的可见 Alpha 与空 Selection 检查由实际执行阶段唯一一次栅格化完成。因此空 Selection 的提示会从打开菜单前移动到点击 Shape 后。

### 3. 同一执行阶段显式复用 RGBA 与 Selection Mask

完成一次读取和栅格化后，Operator 把现成的 RGBA 与 Selection Mask 显式传给图片编辑、Selection 输入导出、Cutout 颜色图和几何 helper。相关 helper 不再从 Blender Image 隐式读取同一像素，也不再接收 Path 后自行构建 Mask。

本地同步流程在一个调用栈内直接复用数据。AI Job 响应产生的 refined Selection 属于新的 Job 结果，不与提交前的手势 Selection 合并为同一个缓存生命周期；本次只移除同一阶段内语义相同的重复处理。

### 4. JSON 只保留在 Cutout 跨 Operator 边界

Lasso 或双击完成后，`SelectCutoutSelection` 把内存中的 `SelectionPath` 直接交给 `open_shape_pie`。菜单调用一次 `to_json()`，将得到的同一个字符串写入每个 `CutoutSelectionToShape` 按钮。用户点击按钮后，新 Operator 通过 `from_json()` 恢复 Path 并进入实际 Shape 生成。

保留这一次 JSON 编码是因为 Blender Operator Property 不能直接保存 Python dataclass，也没有适合任意长度套索点的简单标量 Property。彻底删除 JSON 需要全局状态、令牌或额外 PropertyGroup，复杂度高于这次轻量编码。`to_json()` / `from_json()` 因此保留，但只服务 Cutout Pie Menu 到 Shape Operator 的传值，不再属于通用用户圈选主链。

### 5. 用阶段边界和调用次数验证

交互测试替换像素读取与 `rasterize_selection_path` 入口，验证 Lasso、双击和 Pie Menu 构建阶段调用次数均为零；点击 Shape 或提交 Image Tool 后，每次实际操作各调用一次。结果等价性继续由现有 Image 编辑、Selection 与 Cutout 几何测试覆盖，不设置依赖机器性能的耗时阈值。

## Risks / Trade-offs

- [空 Selection 反馈推迟到点击 Shape 后] → 保留 Path 结构的即时验证，仅推迟必须读取整图的可见性检查。
- [helper 继续隐式读取像素导致单次处理失效] → 删除隐式回退参数并迁移全部调用方，以调用次数测试固定边界。
- [Path JSON 在菜单按钮间复制] → 只编码一次并复用同一个字符串；数据量仅与手势点数相关，远小于 RGBA 和 Mask。
- [Image Tool 的私有 Path 状态被 `execute` 重入] → 把实际图片编辑拆为显式接收 Selection Path 的业务方法，测试直接覆盖该方法，不依赖 Operator 重建后的临时属性。

## Migration Plan

1. 将共享手势完成边界改为传递内存 `SelectionPath`，让 Image Tool 直接进入实际编辑方法，删除其 JSON Property。
2. 调整 Cutout 提交与 `open_shape_pie`，仅在创建 Shape 按钮时编码一次 Path，并由 `CutoutSelectionToShape` 接收。
3. 删除菜单前 Selection 像素验证，让 `CutoutSelectionToShape.execute` 成为唯一 Path-to-Mask 边界。
4. 调整 Image Tool 与共享 helper，显式传递并复用 RGBA 和 Selection Mask。
5. 更新交互、调用次数、结果等价性测试和内部文档。
6. 运行相关测试与全部测试；若回退，整体恢复原调用链，不保留双路径或兼容层。
