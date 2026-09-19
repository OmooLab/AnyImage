## Context

Mask 的 Lasso、Brush 与 Polyline 共用 `ImageGesture`。第一版 Brush 实时预览在 Modal 期间创建同尺寸 Generated Image，并以最多 30 FPS 更新 Pixel Buffer；4K 实测表明 `image.update()` 仍可能上传完整纹理，频繁更新会造成明显卡顿，红色填充 Overlay 也会随着 Flush 时机出现或消失。

因此 Brush 回到与 Lasso、Polyline 一致的事务边界：手势期间只保留简化后的屏幕轨迹并绘制几何 Overlay，不读取、创建或修改 Image；鼠标释放后才投影和栅格化完整笔画，创建一个最终 Image 并替换 active Image Empty。

Keep Original 与 Refine Selection 已无运行时代码，但测试中仍有旧字段缺席断言和一个多余参数。`SelectionPath.invert` 也已无生产调用方，却继续扩大 JSON 协议并让栅格器保留完整画布反选分支。

## Goals / Non-Goals

**Goals:**

- Brush 拖动期间显示与 Lasso、Polyline 相同的虚线和 Mode 填充，不更新 active Image Empty。
- Overlay 与释放提交复用同一组 Brush Primitive 和 union 语义，保证预览范围就是最终 Selection。
- 增加与原 Crop Polyline 手势一致、但使用当前 Mask 术语和 Alpha 主链的 Polyline。
- 将 Mask 默认 Mode 改为 Subtract。
- 删除 Keep Original、Refine Selection、Selection Invert 的剩余状态和历史测试噪音。

**Non-Goals:**

- Lasso 与 Polyline 在路径闭合前只显示几何 Overlay，不实时修改 Image Alpha。
- 不编辑共享源 Image 的 Pixel Buffer，不改变 Frame、Rectify、Cutout Shape 或 Server 行为。
- 不在 Modal 拖动阶段创建预览 Image、读取源 RGBA 或执行图片级计算。
- 不增加 Pillow、OpenCV 或 GPU Compute 依赖。

## Decisions

### 1. Brush 拖动阶段只维护屏幕轨迹

Brush 确认开始编辑后只保存屏幕坐标。鼠标移动使用与 Lasso 相同的最小距离和近共线简化，避免静止事件或直线移动积累冗余点。Modal 期间不调用 `image_rgba()`、`bpy.data.images.new()`、Pixel Buffer 写入、`image.update()` 或 `pack()`，active Image Empty 始终引用原 Image。

RMB、Esc、工具切换和异常只移除 Draw Handler 并结束 Operator，不需要临时 Image 恢复或数据块清理。这样拖动性能只与 Viewport Overlay 和简化后的屏幕轨迹有关，不随图片分辨率变化。

### 2. Overlay 与提交共享 Brush Primitive Union

简化后的中心轨迹生成一组稳定 Primitive：每个采样点对应一个圆，每对相邻点对应一个等宽连接条。Viewport 在 screen space 对这些 Primitive 做 union；鼠标释放后把同一组 Primitive 投影到图片，逐个栅格化并以逐像素 `max` 合入单个覆盖画布。转向、折返与交错都由圆和连接条的并集定义，不再从中心线偏移出一个可能改变 winding 的自交多边形，因此不会产生 miter 尖角或未填充三角。

Selection 完成后读取一次源 RGBA，并根据操作开始 Alpha `A0` 与 Mask `M` 合成：

```text
Set       A' = A0 × M
Add       A' = max(A0, M)
Subtract  A' = A0 × (1 - M)
```

`apply_alpha_mask()` 使用同一纯 Alpha 合成函数；释放阶段只保留一个累计覆盖画布，不保存逐 Primitive Mask 列表。

不选择在每次刷新时重新栅格化完整轨迹，因为成本随轨迹长度持续增加；也不保存每个 Primitive 的独立 Mask，因为内存会随鼠标事件数增长。

### 3. Brush 使用与 Lasso、Polyline 相同的 Overlay

Viewport Overlay 在每个有效移动事件后，把全部 Brush Primitive 在局部屏幕 bounds 内以 2 px scanline bands 做区间 union，再由合并 bands 生成填充三角形，并从相邻 bands 的边界差异连接出闭合外轮廓。内部重叠边和 band 接缝不会进入虚线，急转与交错区域保持连续填充。该过程只处理 Viewport 坐标，不读取或栅格化源 Image。

Subtract 使用红色半透明填充，Set 与 Add 使用灰色半透明填充；虚线保持相同样式。Overlay 不随任何 Image 状态变化，并让用户在释放前看清即将作用的准确区域。

### 4. Polyline 是 Mask 的第三种 Gesture

`mask_gesture_property()` 增加 `POLYLINE`，单一 Mask WorkspaceTool 和 `EditImageAlpha` Operator 保持不变。`ImageGesture` 恢复无 Crop 术语的 Polyline 状态机：首次点击建立起点，后续左键提交顶点，鼠标移动预览下一条边；至少三个点后，点击起点 8 px 范围或按 Enter 完成，Backspace 删除最后一点，RMB/Esc 取消。

完成后把已提交顶点转换为一个 `SelectionPath`，与 Lasso 一样栅格化并进入当前 Mode 的 Alpha 合成。Radius 只属于 Brush；Polyline Tool Settings 只显示 Gesture 与 Mode。

### 5. SelectionPath 只保存 Points

删除 `SelectionPath.invert`、JSON 中的 `invert`、完整画布反选 bounds 和 `1 - mask` 分支。Cutout 的 Lasso 与双击整图都已经提供正向 Path，不需要迁移运行时状态。JSON 继续用于 Cutout Operator 间传值，但只包含 `points`。

删除重复验证 Keep Original、Refine Selection 和旧 Crop 字段缺席的历史断言；仍通过当前 Scene Property、Operator annotation、Job request 和打包文件的正向精确集合测试固定公开边界。测试夹具中的多余 `keep_original=False` 同步删除。

## Risks / Trade-offs

- [高分辨率图片会让释放后的提交耗时可感知] → 将图片级投影、栅格化和结果创建集中到一次释放事件，避免拖动期间反复上传纹理。
- [长而复杂的笔画会保留较多屏幕点] → 使用与 Lasso 相同的距离与近共线简化，只保留表达轨迹形状所需的点。
- [Set 模式会让笔画外 Alpha 归零] → 保持既有 Set 公式；默认 Subtract 仍覆盖最常用的擦除行为。
- [复杂笔画包含大量重叠 Primitive] → screen-space scanline 先合并每个 band 的区间，再生成一次填充和外轮廓；图片空间只在释放时使用单个累计覆盖画布。
- [Polyline PRESS 事件与对象点选冲突] → 沿用 `resolve_image_edit_click()`，首次点击另一对象只切换 active，再次点击当前 Image 才开始手势。

## Migration Plan

先完成已实现的 `replace-crop-with-mask-and-rectify` 作为基线。实现时先精简 SelectionPath，再加入 Polyline 状态机，随后实现 Brush 虚线 Overlay 与释放栅格化，最后删除失去调用方的 Helper 和历史测试。Scene 中未显式保存 Mode 的文件自动使用新的 Subtract 默认值；已经保存的 Mode 值保持不变。

回滚时可恢复本 change 前的 Mask 实现；它不迁移持久文件、Server 数据或 Blender Object 结构。

## Open Questions

无。4K 实测决定拖动阶段不再更新 Image；后续实测进一步要求 Overlay 与提交共享圆角 footprint，并恢复 Mode 填充。
