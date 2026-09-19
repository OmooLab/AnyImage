## Context

Plane、Depth Plane 与 Cutout 的非 Shadeless 材质都由 `common/material.py` 创建，但 `O Image Layer` 的颜色当前只驱动 Base Color、Subsurface Radius、Emission Color 与 Roughness，Principled BSDF 的 IOR Level 保持常量。Depth Plane 与两个 Depth Cutout 子组把相机参考深度公开为 `Base Plane Depth`，而实现和元数据已经统一使用 `reference_depth`。

Refine Selection 当前把 Selection bounds 内的矩形 RGBA 交给 BEN2，并由 `preserve_input_alpha=True` 得到 `Source Alpha × BEN2 Alpha`，随后 Server 会按可见 Alpha 紧裁切并返回新的局部 bounds。Cutout 在启用 Refine 后直接用 BEN2 Alpha 构建网格，丢失了用户的 Selection Mask；Crop 也直接采用 BEN2 输出。与此同时，Cutout 的 MoGe-2、Normal 与 Depth 需要完整的 Refine 内容范围，不应被 Selection Mask 限制。

## Goals / Non-Goals

**Goals:**

- 让生成材质的暗色区域通过 IOR Level 降低高亮。
- 将 Geometry Nodes 的参考深度接口统一为与实现一致的 `Reference Depth`。
- 固定 Refine 输入与输出的矩形尺寸和 placement bounds。
- 让 Cutout 的 Color、Normal 与 Depth 共享 `Source Alpha × BEN2 Alpha` 内容范围。
- 让 Selection Mask 只约束最终 Crop 图片或 Cutout 网格。

**Non-Goals:**

- 不改变 BEN2、MoGe-2、Normal 或 Depth 模型实现和推理分辨率。
- 不用 Selection Mask 限制 BEN2、MoGe-2 或任何 Cutout 贴图的生成范围。
- 不改变 Depth EXR 的连续 RGB Field 或 MoGe-2 Validity Alpha 语义。
- 不为旧 Geometry Nodes socket 名称、旧 Job 结果 key 或旧节点资产保留兼容层。
- 不改变普通本地 Crop、普通本地 Cutout 或 Shadeless 材质。

## Decisions

### 1. `O Image Layer` Color 直接驱动 IOR Level

在 `create_image_material()` 的 Principled 分支中，将 `O Image Layer` 的 Color 输出直接连接到 Principled BSDF 的 IOR Level。Blender 按 Color-to-Float 规则完成转换，因此黑色得到 `0`、白色得到 `1`；既有 IOR 数值继续独立控制 Fresnel 模型。该公共入口只被 Plane、Depth Plane 与 Cutout 使用，因此无需新增调用参数或材质节点组 socket。

相比新增亮度 Math 节点或只降低默认值，直接连接准确表达颜色层驱动关系，节点更少，也让暗色抑制与原图连续变化。

### 2. 公开接口统一使用 `Reference Depth`

将 `O Image Depth Plane`、`O Image Cutout`、Depth Balloon 与 Depth Surface 的 `Base Plane Depth` socket 全部改名为 `Reference Depth`。Modifier 初始化与节点间连线按新名称直接迁移，内部 `reference_depth` 变量和 `depth.json` 字段保持不变。

相比 `Base Depth`，`Reference Depth` 更准确说明该值是采样深度的运算基准，并与现有代码和元数据术语一致。节点资产随构建脚本重新生成，不保留旧 socket。

### 3. Refine 输出保持提交前的完整矩形画布

`server/selection/refine_selection.py` 只运行 BEN2 并保存与输入相同尺寸的 RGBA，不再按 Alpha 调用紧裁切，也不返回局部 bounds。`refine-image-selection` 和 Cutout artifact Job 删除 `selection_bounds` 产物；Blender 调用方继续使用提交前保存的 Selection bounds 进行 placement。

BEN2 继续使用 `preserve_input_alpha=True`，因此统一 Refine 内容 Alpha 定义为：

```text
refined_alpha = source_alpha × ben2_alpha
```

Server 不接收 SelectionPath、SelectionMask 或 Mask sidecar。相比在 Server 组合 Selection Mask，稳定矩形输出让同一 Refine 结果可以直接服务 Color、Normal 与 Depth，并保持 AI 与用户几何约束分离。

### 4. Cutout 贴图共享 Refine 内容，网格再乘 Selection Mask

启用 Refine 时，Cutout artifact Job 将完整 BEN2 RGBA 同时作为最终 Color 和 MoGe-2 输入。Normal 的可见区域、Depth Metadata 的参考内容区域，以及 MoGe-2 黑底合成均继续从该图片 Alpha 派生。Depth EXR RGB 仍保存完整连续 Field，Alpha 仍只保存 `GeometryFrame.validity`。

Blender 响应阶段读取完整 BEN2 Alpha，并与提交时已栅格化的 `SelectionMask.values` 逐像素相乘：

```text
mesh_content = source_alpha × ben2_alpha × selection_mask
```

由于 Refine 结果保持原 bounds，两个数组尺寸天然一致，不再需要局部 bounds 偏移或 Mask 重采样。组合结果只传给 BaseShape 构建、内容空值检查和网格标定；颜色图片及 Normal、Depth 贴图保持未乘 Selection Mask。

未启用 Refine、但因 Normal 或 Depth 提交 Job 的 Cutout 继续使用完整 bounds 输入，并在 Blender 中执行 `source_alpha × selection_mask`。两条 Cutout 响应路径因此都由同一个“贴图 Alpha × Selection Mask”入口构建网格。

### 5. Crop 在 Blender 中应用 Selection Mask

Crop Refine 同样接收完整 BEN2 RGBA，并沿用提交前 bounds。由于 Crop 的最终产物是图片而不是网格，Blender 必须把 BEN2 输出 Alpha 与原始 Selection Mask 相乘后创建结果图片：

```text
crop_alpha = source_alpha × ben2_alpha × selection_mask
```

Selection 栅格化仍只执行一次。Crop 提交阶段把局部 Mask 值写入与 Bounds 输入同一临时容器的本地 sidecar；该路径只由 Blender 响应读取，不进入 Job request。响应完成 Alpha 组合与结果 Image 创建后统一清理临时容器。相比把 Mask 发送到 Server或再次栅格化 SelectionPath，这保持了 Server 边界和一次栅格化约束。

Crop 结果画布和 placement bounds 保持提交前 Selection bounds，不再按组合后的可见 Alpha紧裁切。

## Risks / Trade-offs

- [直接连接 Color 会让亮色 IOR Level 高于原默认 `0.5`] → 这是明确的颜色驱动语义；节点测试固定直连关系，不额外缩放。
- [Geometry Nodes socket 改名会断开依赖旧接口名的内部设置] → 同步修改所有构建、验证、Modifier 设置和已存节点资产，不保留双 socket。
- [Refine 图片不再紧裁切，透明边缘画布可能更大] → bounds 本来已限定为用户 Selection 的矩形范围，接受稳定对齐换取的少量图片尺寸成本。
- [Crop Mask sidecar 增加一份临时文件] → 与 Bounds 输入共用生命周期，只保存单通道局部值，并由统一 cleanup 删除。
- [Cutout 贴图含有 Selection 外的 BEN2 内容] → 最终网格由组合 Mask 严格限制，网格外纹理不会形成可见表面；AI 保留完整上下文是预期行为。
- [Depth 的“统一内容范围”被误解为覆盖 EXR Alpha] → 测试和文档明确区分业务内容 Alpha 与模型 Validity，保持连续 Field 协议不变。

## Migration Plan

1. 先修改 Refine Server 输出协议和测试，删除紧裁切与局部 bounds 产物。
2. 调整 Crop 与 Cutout Blender 响应，以提交前 bounds 对齐 Mask 并构建最终图片或网格。
3. 增加材质 Color-to-IOR-Level 连接及测试。
4. 一次性重命名所有 Geometry Nodes socket、调用方和验证断言，重新构建并验证节点资产。
5. 更新内部文档并运行相关测试和完整测试。

回退时整体恢复旧 Refine bounds 协议、旧 socket 名称和旧节点资产，不保留新旧并行入口。

## Open Questions

无。
