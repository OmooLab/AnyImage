## Context

当前 `operators/crop_tool/` 同时承载 Frame、Lasso、Polyline 与 Perspective。Lasso 和 Polyline 把一次几何 Selection 乘入源 Alpha，随后按可见内容紧裁切并调整 Image Empty 画框；Lasso 还可以提交 BEN2 Refine Job。三个 Crop 子工具分别保存 Keep Original，公共 `CropSelectionGesture` 因而混合了工具设置、Lasso/Polyline 交互和 Cutout 复用职责。

新交互把 Alpha 视为可反复编辑的当前状态：Mask 用 Lasso 或 Brush 生成一次手势 Mask，再以 Set、Add 或 Subtract 合成 Alpha。Frame、Mask、Rectify 是同一个简短的 Image Edit 工具组。当前工作区的 `standardize-cutout-z-axis` 同时修改 Cutout 主链，实施本 change 时应以该 change 完成后的 Cutout 结构为基线。

## Goals / Non-Goals

**Goals:**

- 用 **Frame / Mask / Rectify** 表达三个工具的真实产物，并删除全部旧 Crop 工具标识。
- 让一个 Mask WorkSpaceTool 和一个业务 Operator 承载 Lasso、Brush 及统一 Alpha 合成。
- 让 Mask 的图片尺寸、Image Empty 身份和矩形画框在每次编辑后保持不变。
- 删除 Crop/Cutout Refine Selection 与 Crop Keep Original 的完整参数和执行路径。
- 保留 Rectify 已有的四点透视校正、宽高比、输出限制和 Alpha trim 行为。

**Non-Goals:**

- 不为 Mask 维护独立 Blender Mask、Selection 历史或隐藏的原始 Alpha 副本。
- 不让 Cutout 使用 Brush、Set/Add/Subtract，Cutout 继续以单次 Lasso 定义 Shape 范围。
- 不改变 Frame 合成、Rectify Homography、Cutout Shape、Depth、Normal Map 或 Remove Background。
- 不为已删除的类、Operator ID、Tool ID、属性或 Job 保留兼容层。

## Decisions

### 1. 用 Image Edit 模块承载 Frame、Mask、Rectify

将 `operators/crop_tool/` 改为与业务边界一致的 `operators/image_edit_tool/`，内部文件使用 `frame.py`、`mask.py` 和 `rectify.py`。注册顺序固定为 Frame、Mask、Rectify，Frame 继续作为工具组首项；Cutout 保持为相邻的独立工具。

公开名称和 ID 只保留当前术语：`MaskTool`、`EditImageAlpha`、`RectifyTool`、`RectifyImagePerspective`，以及 `anyimage.mask`、`anyimage.edit_image_alpha`、`anyimage.rectify`、`anyimage.rectify_image_perspective`。激活入口改为 Image Edit 语义并默认选择 Frame。

不选择继续使用 Crop 模块并只修改标签，因为源码边界、状态属性和错误信息仍会表达已经不存在的裁切模型。

### 2. 一个 Mask Tool 读取 Gesture、Mode 与 Radius

Scene 设置保存 `mask_gesture`、`mask_mode` 和 `mask_radius`：Gesture 为 `LASSO` 或 `BRUSH`，Mode 为 `SET`、`ADD` 或 `SUBTRACT`，Radius 是 Brush 使用的正整数屏幕像素，默认 25 px。Tool Settings 以展开的三个图标显示 Mode；Radius 仅在 Brush 时显示。

Mask 只有一个 WorkSpaceTool 和一个 Operator。Operator 在 invoke 时冻结三个设置；Lasso 收集并闭合自由手绘路径，Brush 收集连续笔画并显示当前 Radius 圆环。单击 Brush 生成一个圆形印记，拖动时相邻采样之间生成连续覆盖，不因鼠标事件间距留下空洞。两种手势最终都只产生一个 `SelectionMask` 并进入同一个 Alpha 合成入口。

不选择两个 WorkSpaceTool，因为它们只有手势采集不同，分开后会重复模式、结果和设置逻辑，也不符合用户在当前 Tool 内切换 Gesture 的预期。

### 3. 直接以当前 Alpha 和本次手势 Mask 合成

设当前像素 Alpha 为 `A`，本次带边缘权重的手势 Mask 为 `M`：

```text
Set       A' = A × M
Add       A' = max(A, M)
Subtract  A' = A × (1 - M)
```

所有运算逐像素限制在 `0–1`，RGB 原样复制。Set 保留本次手势内的当前可见内容；Add 可以重新提高已擦除区域的 Alpha；Subtract 降低本次手势覆盖区域的 Alpha。因为不保存初始 Alpha，Add 以本次 Mask 权重为恢复值，可能高于图片导入时的 Alpha；这是直接编辑当前 Alpha 的明确语义。

不选择保存隐藏的原始 Alpha，因为它会引入跨图片替换的额外状态、生命周期和同步规则，也会让 Add 不再是直接的 Alpha 涂抹。

### 4. Mask 始终替换同尺寸图片而不改变画框

Mask 读取完整当前 RGBA，应用 Alpha 合成后创建相同宽高的 packed Image，并用公共图片替换入口赋给 active Image Empty。它不传 `placement_bounds`，因此对象 identity、matrix、display size 和 image offset 不变；共享旧 Image 的其他对象继续引用旧数据。即使结果 Alpha 全部为零也允许完成，仍作为一个 Undo 步骤。

删除 Mask 的紧裁切和空 Alpha 拒绝逻辑。Rectify 仍可按自身业务生成不同尺寸并通过 placement bounds 对齐，因此“稳定画框”只属于 Mask。

### 5. Brush Radius 使用 Viewport 屏幕像素

Radius 与 Blender Circle Select 一样以 Region 屏幕像素表达，使圆形预览与用户看到的范围一致，不受图片分辨率影响。Brush 将屏幕笔画分解为相邻线段的圆角胶囊和端点圆形，在图片平面投影后合并局部 Mask；图片外覆盖被裁掉。实现复用 SelectionMask 的 bounds/value 表示和公共抗锯齿规则，不引入 Pillow、OpenCV 或几何依赖。

不选择图片像素 Radius，因为同一设置会随图片分辨率和 Viewport 缩放产生明显不同的屏幕笔刷尺寸。

### 6. Rectify 只更换业务名称并删除 Keep Original

Perspective 的四点采集、凸 Quad 规范化、512 px 预览、目标宽高比、分块 Homography、8192 px 长边限制、总像素限制、可见 Alpha trim 和结果 placement 保持不变。类、ID、状态文本、warning、Undo 名称、文档和测试统一改为 Rectify；完成后直接替换 active Image Empty，不再复制源对象。

不选择 `Perspective`，因为它只描述概念；`Rectify` 用一个单词表达把透视四边形校正为矩形的动作，并与 Frame、Mask 的长度一致。

### 7. 完整移除 Refine Selection 和 Keep Original 路径

Mask 删除 BEN2 属性、AI readiness、临时 bounds 输入、SelectionMask sidecar、异步响应 Operator 和 `refine-image-selection` Job。Cutout 删除对应工具设置、Pie 参数、Operator 参数和 `refine_model` 请求；需要 Depth 或 Normal 时继续提交原始 Selection bounds 矩形，颜色图直接复用该输入。

Server Cutout Job 不再导入或执行 refine，删除专用 Job 注册、Job 文件和只为该能力存在的 `server/selection/` 封装。BEN2 模型、缓存、Remove Background 与 Debug 保留。

删除三个旧 Crop Keep Original 属性和 Operator 参数。`place_empty_image_result()` 若不再有调用方则删除，由 Mask 和 Rectify 直接复用 `replace_empty_image()`；不保留复制结果对象的公共胶水代码。

## Risks / Trade-offs

- [Add 会让原本透明的像素变得可见] → 文档和公式明确它直接涂抹当前 Alpha；RGB 始终保留，Undo 提供操作级恢复。
- [屏幕圆形投影到倾斜图片后不再是图片像素圆形] → 以 Viewport 视觉范围为准，并用投影后的胶囊覆盖测试倾斜与缩放图片。
- [快速拖动产生断裂笔画] → 以相邻事件线段生成连续胶囊，而不是只绘制离散圆点。
- [模块和 ID 全量改名遗漏注册或注销] → 参数化检查类导出、工具顺序、Operator ID、状态文本、打包内容和逆序注销。
- [删除 Refine 时误删 BEN2 公共能力] → 测试固定 Remove Background、BEN2 Debug、模型目录和打包内容仍存在。
- [与 Cutout Z 轴 change 修改同一文件] → 先完成 `standardize-cutout-z-axis`，再基于其最终 `main.py`、测试和文档移除 Refine 分支。

## Migration Plan

1. 先完成并验证 `standardize-cutout-z-axis`，冻结本 change 的 Cutout 基线。
2. 将 Crop 模块与公共命名迁移为 Image Edit，注册 Frame / Mask / Rectify 并删除 Polyline 和旧 ID。
3. 实现 Mask 设置、Lasso/Brush 手势、统一 Alpha 合成和稳定画布结果，删除 Keep Original。
4. 将 Perspective 完整改名为 Rectify，保留 Homography 行为并删除 Keep Original。
5. 删除 Blender 与 Server 两侧 Refine Selection 路径，验证 Cutout 的本地、Depth 和 Normal 分支。
6. 更新测试与当前文档并运行完整测试；不构建节点资产、文档站点或发布包。

回退必须整体恢复旧 Crop 模块、工具注册、属性、Refine Job 和文档，避免 Blender 请求已删除的 Server Job 或注册不存在的 Tool ID。

## Open Questions

无。
