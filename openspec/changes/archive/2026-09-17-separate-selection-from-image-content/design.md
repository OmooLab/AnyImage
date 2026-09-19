## Context

`rasterize_selection_path()` 当前同时完成路径填充、抗锯齿、源 Alpha 相交、空内容判断和内容 bounds 收紧。调用方因此必须先通过 Blender `Image.pixels` 取得 RGBA，导致 `SelectionMask` 随图片透明度变化，而不是稳定表达用户圈选。

Image Tool 与 Cutout 的实际业务确实需要图片内容，但目的不同：本地编辑要把 Selection 乘入源 Alpha，Cutout 几何要用内容 Mask，AI 操作要把局部图片写成 Job 输入。需要 AI 时，现有代码先把 Lasso Mask 乘入临时 RGBA 并编码 PNG；响应后又读取源图并新建颜色 Image，造成同一操作中的第二次大图编码。实测 6288×5920 RGBA PNG 的 Selection 栅格化约 0.17–0.55 秒，提交前 PNG 保存约 1.79 秒，新建颜色 Image 的 Pack 约 1.74 秒。图片编码成本不属于 Selection，并且本设计接受生成新图片所需的单次编码成本。

## Goals / Non-Goals

**Goals:**

- 让 SelectionPath 与 SelectionMask 只表达用户圈选几何，不受源图片 Alpha 或颜色影响。
- 让 Image Tool、Cutout 与 AI 输入准备在各自业务边界显式消费源 Alpha 或 RGBA。
- 所有 AI 操作统一使用 Selection 几何 bounds 内、未乘 Lasso Mask 的矩形局部 RGBA 文件。
- 复用提交前输入或 Refine 输出的已有编码图片，避免 AI 响应阶段重新构建并编码相同颜色图。
- 保持 non-zero winding、Invert、抗锯齿和局部画布语义。

**Non-Goals:**

- 不优化生成新图片时不可避免的 PNG 编码、Pack 或磁盘写入耗时。
- 不按 FILE、Packed、Generated 或 Dirty 来源建立不同的 Operator 主链。
- 不引入 Pillow、GPU readback、后台 Blender 数据访问或新的运行时依赖。
- 不改变 SelectionPath JSON、AI 模型、Cutout Shape 算法或 Job 进程边界。

## Decisions

### 1. Selection 栅格化只产生几何 Mask

`rasterize_selection_path(image_size, selection_path, *, antialias=False)` 只根据路径、Invert、图片尺寸和抗锯齿生成 `SelectionMask(values, bounds)`。删除 `source_alpha` 与 `alpha_threshold` 参数，栅格器不导入 Blender Image helper，也不执行内容可见性检查。

普通 Selection 的 bounds 来自路径与抗锯齿 padding 裁切到图片范围；Invert 仍使用整张图片。相同 Path、尺寸和抗锯齿设置必须在透明、半透明与不透明图片上得到完全相同的 SelectionMask。

相比保留可选 Alpha 参数，彻底删除内容入口可以固定职责并阻止调用方继续把内容 bounds 误当成 Selection bounds；不保留兼容调用方式。

### 2. 图片业务直接合并局部 Alpha 与 Selection 值

Image Tool 在 `SelectionMask.bounds` 内裁切源 RGBA，并直接执行 `local_alpha *= selection_values`。最终内容 bounds、空内容和结果图片创建都属于 Image 编辑业务。实现应在已有局部数组上计算行列可见范围，不为每个可见像素生成坐标数组，也不把内容相交结果写回 SelectionMask。

本地 Cutout 在构建 BaseShape 时显式组合局部源 Alpha 与 Selection 值；颜色、几何和空内容判断使用该业务结果。SelectionMask 本身在调用链中保持不变。相比新增第二种与 SelectionMask 同形的公共值类型，业务直接消费两个一通道局部数组更简单，也避免把图片内容重新包装成“Selection”。

### 3. AI 输入是 Selection bounds 的原始矩形 RGBA

将当前“Selection 输入”改为“Bounds 图片输入”：公共图片 helper 接收源 RGBA 与几何 bounds，只裁切并写出矩形 RGBA，不把 SelectionMask 乘入 Alpha。Image Tool、Cutout Refine、Normal 与 Depth 都调用同一个入口；来源已经统一为 Blender Image，不在 Operator 中按文件、Packed 或生成图片分流。

Refine 把 Lasso 当作上下文范围。BEN2 可以在该矩形内保留 Lasso 外的内容，其输出 Alpha 是 Refine 业务结果，不再与原始 Lasso Mask 相交。Normal 或 Depth 也消费同一矩形输入，最终 Shape 仍由本地 Selection 几何约束。

Invert Selection 的几何 bounds 是全图，因此其 AI 输入自然退化为全图矩形，不增加特殊协议。

### 4. 已编码的 AI 图片直接成为颜色资产

AI 响应选择一个已有文件作为最终局部颜色图：启用 Refine 时使用 BEN2 输出；仅生成 Normal 或 Depth 时使用提交前的 Bounds 输入。Blender 直接加载该文件，继承源颜色空间和 Alpha 约定，Pack 已编码文件后交给 Image Empty 或 Cutout 材质。

Image Tool Refine 直接按响应 bounds 替换源 Image Empty，不再提取输出 Alpha、重新读取源 RGBA、创建 Pixel Result Image。Cutout 从同一个局部文件读取需要的 Alpha 构建几何，并把该已加载 Image 用作颜色纹理，不再调用 `_cropped_color_image()` 重建同一颜色内容。

输入临时文件必须保持到响应完成且 Blender 已加载并 Pack；随后由现有 Job 清理生命周期删除。相比继续从原图重建，这一方案保持颜色来源一致，并把已有文件 Pack 从大图重新编码变为文件收纳。

### 5. 内容错误由消费业务报告

纯 Selection 只在路径与图片范围没有几何交集时报告空 Selection。源 Alpha 全透明、Image 编辑结果为空、Refine 输出为空或 Cutout 内容 Mask 为空，分别由执行该内容操作的业务报告。这样错误发生位置与实际失败职责一致。

## Risks / Trade-offs

- [Refine 结果扩展到 Lasso 外] → 这是明确接受的产品语义；测试固定 Lasso 只提供矩形上下文，不作为 Refine 硬 Mask。
- [Selection bounds 不再等于内容 bounds] → 在类型和文档中只把 SelectionMask bounds 称为几何 bounds，内容业务独立计算并传递 placement bounds。
- [AI 输入矩形包含额外背景] → 最终本地 Shape 仍受 Selection 几何约束；Refine 则有意允许模型利用并保留矩形上下文。
- [复用 PNG 改变颜色空间或 Alpha 配置] → 加载后显式继承源 Image 的颜色空间与 Alpha mode，并用结果等价测试覆盖。
- [临时文件被过早清理] → 保持现有 Job cleanup 边界，只有成功加载并 Pack 或操作取消后才删除输入。
- [全图或 Invert 仍需处理大图] → 接受单次新图片编码成本，本次只删除 Selection 的内容依赖和 AI 响应阶段的重复编码。

## Migration Plan

1. 修改 Selection 栅格 API 与测试，使其只产生几何 Mask，并迁移所有调用方。
2. 将 Image Tool 与本地 Cutout 的源 Alpha 合并、内容 bounds 和空内容检查放入各自业务阶段。
3. 将 `prepare_selection_input` 替换为统一的 Bounds 矩形 RGBA 输入，并更新 AI Job 输入语义和测试。
4. 调整 Image Tool 与 Cutout AI 响应，直接加载并 Pack 输入或 Refine 输出，删除源图重读和颜色 Image 重建。
5. 更新内部文档，运行相关测试、完整测试和真实高分辨率阶段基准。

回退时整体恢复旧栅格参数、Masked AI 输入和响应重建链，不保留双入口或兼容层。

## Open Questions

无。

