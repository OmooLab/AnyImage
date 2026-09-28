## Context

Cutout 当前从一张裁切后的颜色图以及可选的 Normal、Depth 产物创建基础网格，基础 `UVMap` 覆盖完整 0–1 区间。普通 Cutout 和 Depth Cutout 的 Balloon、Shell 正厚度路径都会复制或挤出基础表面形成后片；后置对称路径也会镜像输入表面。生成面继承原 UV，因此正片与后片最终采样同一像素。

颜色图由 Blender 端从 Selection bounds 准备，MoGe 仍只接收这一张正面输入并生成 Normal、Depth。Depth metadata 中的图片尺寸与内参描述这次单张正面推理，不能因为材质图片纵向复制而改变。

## Goals / Non-Goals

**Goals:**

- 为所有 Cutout 形态建立固定的纵向双区图片布局：正片在上、后片在下。
- 让基础单片、Balloon、Shell 和后置对称路径使用同一 UV 协议。
- 让 Color 与 Normal 使用相同的材质 Atlas，同时保持 Depth 与 AI 推理为单区。
- 保持单一材质、现有材质节点与现有节点组公开接口。
- 让零厚度单片只采样正片上区，并让 Side 按 Front、Rear 的实际挤出来源分别采样对应区域，不产生前后渐变。

**Non-Goals:**

- 不生成真实的背面图像、背面深度预测或独立背面法线。
- 不让用户选择 Atlas 方向，不增加 UDIM、材质槽或 UV 布局开关。
- 不在侧壁混合正背纹理，也不新增侧壁专用纹理区域。
- 不改变厚度、Split、边界平滑、法线空间或可见几何外形；允许普通 Cutout 为分离 Side UV 增加必要的中圈拓扑。

## Decisions

### 1. 固定使用上下双区布局

Color 与 Normal 尺寸为 `W × 2H`：上半区为原图，下半区为水平镜像。厚度生成的 Front 映射为 `(u, 0.5 + 0.5v)`，Rear 映射为 `(1-u, 0.5v)`。后置对称不重新分配 tile，Retained side 与 Mirrored side 保留完全相同的输入 UV。

固定布局避免为每张材质图片保存方向元数据，也使 Color、Normal 和所有节点组使用同一变换。没有采用自适应横向或纵向布局，因为它会把布局选择传播到图片加载、节点输入和测试。

### 2. AI 始终只消费未复制的正面

Blender 先准备单张正面颜色图，并将它直接作为 AI 分析输入。Server 保持既有职责，对该正面执行一次推理并写出单区 Normal 与 Depth；Blender 收到结果后把 Color、Normal 组成双区材质 Atlas，Depth 保持单区。`depth.json` 的 `image_size` 与 intrinsics 继续描述服务端返回的 `W × H` 正面图片。

Blender 端的 Alpha 在 Atlas 建立前读取单区 Color；参考深度、中位深度和对称方向拟合直接读取单区 Depth，不引入双区兼容分支。

没有让 MoGe 接收拼接图片，因为这会重复推理、改变相机画幅并在中线制造无意义的图像边界。

### 3. 基础 UV 从创建时就位于上半区

`create_shape_object()` 写入 `UVMap` 时将 BaseShape 的 0–1 UV 缩放并偏移到上半区。Depth、Normal 和颜色消费者因而从一开始就使用同一正片坐标。零厚度路径直接输出该 UV，不需要额外分支或材质映射。

Cutout 几何算法需要归一化源坐标时，由 Cutout 调用点显式还原单 tile UV，不能把 Atlas V 当作原始相机 V。共享的 Depth Surface 采样保持完整 0–1 UV，避免改变 Depth Plane；材质图片采样则直接使用上半区 UV。

### 4. 后片与两侧 Side 在生成位置分区

各节点组在已经识别 Front、Rear 与 Side 的构造位置处理 `FLOAT2/CORNER` UV：

- Front 保持上半区坐标；
- Rear 在继承 Front UV 后将 U 映射为 `1-u`，并将 V 减去 `0.5`；
- 从 Front 叶片挤向共同中圈的 Front-side 使用上半区；
- 从 Rear 叶片挤向共同中圈的 Rear-side 使用下半区；
- 两组 Side 在共同中圈保持位置重合，但使用彼此独立的 Face Corner UV seam。

Depth Cutout 当前已经从两张断开的叶片分别挤向一个共享 Side ring；实现保留这一结构，Front 分支的 Side UV 留在上区，Rear 分支的 Side UV 下移到下区，并让中圈成为 UV seam。叶片先完成既有 UV 平滑，再平移 Rear 及其 Side，避免平滑目标跨越 Atlas 中线。

普通 Cutout 的 Balloon 在轮廓处以 Front、Rear 的重合边闭合，并保留独立 Face Corner UV；Shell 的直壁在几何中点建立共同中圈，分成 Front-side 与 Rear-side。任何单个 Side face 的 corners 都不能分别落入上下 tile。后置对称只复制完整输入：Retained side 和 Mirrored side 各自保留输入中已有的 Front、Rear 与 Side 分类；这里不把对称两侧称为 Front/Rear。

这种分区会在 Side 中点形成硬 UV seam，而不是渐变。上下图片初始相同，因此默认外观连续；用户独立编辑 Rear 后，中圈成为正背材质的明确交界。Face Corner 域允许位置焊接而 UV 保持分离。

### 5. 图片复制保持原数据解释

颜色 Atlas 的 Rear tile 水平镜像 Front，使用单一双高缓冲区控制大图构建时的峰值内存，并保持 byte/float 编码、Alpha、透明区域 RGB、颜色空间与 Alpha Mode。Normal 继续作为 Non-Color；Object Normal 仅镜像像素位置，Tangent Normal 同时反转 X 分量，即编码后的 `R = 1-R`。Depth 继续使用服务端返回的 RGBA float32 单区 EXR。

Color 与 Normal 的 Rear tile 配合翻转后的 Rear UV，使默认采样仍与 Front 逐点对应。现有对象空间背面反射和 Normal Reduction 继续负责最终着色；Depth 后片仍由现有厚度算法产生，不需要第二张 Depth 贴图。

### 6. Boundary Padding 在 Atlas 之前执行

Blender 使用单区 BaseShape mask 对尚未拼接的 Color 与 Depth 执行既有 Boundary Padding，随后才为 Color 建立双区 Atlas。Normal 延续既有行为，不参与 Boundary Padding，只在该阶段之后建立双区 Atlas。

这样 Padding 的像素坐标始终与单区内容 mask 对齐；若先拼接 Color，按双倍高度缩放单区 mask 会把边界源位置映射到错误区域。Depth 保持单区，因此 Padding 后也不拼接。

### 7. 只改变 Cutout 协议

Plane、Depth Plane、Relief Plane、Panorama 与 Clipboard 继续生成单区图片和完整 0–1 UV。双区行为由 Blender 的 Cutout 结果加载和 Cutout 节点资产共同实现，不改变服务端产物或共享入口的默认行为。

## Risks / Trade-offs

- [Cutout Color 与 Normal 的内存和打包体积约翻倍] → 只复制材质图片，不改变 AI 输入、Depth 或其他图片入口。
- [后片平移发生在 UV 平滑前会跨 tile 污染] → 先完成现有叶片 UV 平滑，再按面域身份平移最终 Rear corners。
- [焊接点共享 Point 但需要不同 UV] → 始终在 Face Corner 域写入正片、后片和侧壁 UV，并测试 seam 两侧值。
- [普通 Cutout 的单张 Side face 无法同时属于正背两区] → 在几何中点分成 Front-side 与 Rear-side，共享位置但保留 Face Corner UV seam。
- [Side 中圈在独立编辑背面后产生硬接缝] → 这是本轮无渐变设计的明确交界；默认上下图片相同，因此初始结果连续。
- [普通与深度节点的多条厚度路径漏改] → 结构测试和求值测试同时覆盖 Balloon、Shell、零厚度、正厚度及后置对称。

## Migration Plan

1. 增加 Cutout 专用上下复制和单 tile 读取辅助逻辑，保持共享图片函数默认行为不变。
2. 对单区 Color 与 Depth 执行既有 Boundary Padding，再让 Cutout Color、Normal 采用 `W × 2H` 布局；Depth 与 metadata 保持 `W × H` 单区标定。
3. 将基础 Cutout UV 初始化到上半区，更新所有 CPU 侧 Depth/Alpha/方向计算使用单 tile 语义。
4. 更新普通、Depth 与对称节点组的 Rear、Front-side 和 Rear-side Face Corner UV；普通 Cutout 必要时建立共享中圈。
5. 运行相关 Python 与 Blender 测试，再执行 `uv run --group blender node-group build` 重建并验证节点资产。

本变更直接替换 Cutout 的旧重叠 UV 输出，不保留旧布局开关或兼容节点。

## Open Questions

无。
