## Why

当前 `SelectionPath → SelectionMask` 在栅格化阶段读取并合并源图 Alpha，使选区几何依赖图片内容，也迫使 Image Tool 与 Cutout 在业务开始前读取整图。Selection 应客观表达用户圈选；源 Alpha、图片裁切、AI 输入和最终图片持久化应由实际业务分别处理。

## What Changes

- **BREAKING**：Selection 栅格化只接收图片尺寸与 `SelectionPath`，删除源 Alpha、Alpha threshold 及内容可见性职责；`SelectionMask` 只保存 non-zero winding、Invert 与抗锯齿产生的几何值和几何 bounds。
- Image Tool 与本地 Cutout 在实际操作中显式将局部源 Alpha 与 `SelectionMask.values` 相乘，并在需要时计算内容 bounds；公共 Selection 模块不读取 Blender Image。
- 需要 AI 的 Image Tool 与 Cutout 统一按几何 bounds 写出一份未应用 Lasso Mask 的矩形局部 RGBA 文件。Refine 将 Lasso 作为上下文范围，允许 BEN2 结果保留矩形内、Lasso 外的内容。
- AI 响应复用已经编码的局部图片：Refine 直接使用 BEN2 输出，只有 Normal 或 Depth 时直接使用提交前输入；不再重新读取源图、重建同一颜色 Image 后再次编码 Pack。
- 删除由 Selection 栅格化隐式承担的空内容判断，改由消费源 Alpha 或 AI 结果的具体业务报告空内容。
- 增加 Selection 纯几何等价、Alpha 合并边界、矩形 AI 输入和编码图片复用测试，并同步内部文档。

## Capabilities

### New Capabilities

- `selection-content-processing`: 规定纯几何 Selection Mask、业务侧源 Alpha 合并、Bounds 矩形 AI 输入及已有编码图片复用行为。

### Modified Capabilities

无。

## Impact

- 影响 `common/selection.py`、`common/image.py`、Image Tool、Cutout Tool、Cutout 颜色图创建、AI 输入/响应处理及相关测试和内部文档。
- `rasterize_selection_path()` 的内部调用协议发生变化，不保留带 `source_alpha` 或 `alpha_threshold` 的兼容入口。
- Cutout 与 Image Tool 的 AI 输入 Alpha 语义改变：输入为几何 bounds 内的原始矩形 RGBA，而不是预先乘入 Lasso Mask 的 RGBA。
- 不新增依赖，不改变 SelectionPath JSON、填充规则、抗锯齿核、AI 模型或 Job Server 进程边界；不以本次变更优化不可避免的新图片编码耗时。
