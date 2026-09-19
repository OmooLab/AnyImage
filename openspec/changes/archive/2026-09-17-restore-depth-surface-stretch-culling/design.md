## Context

Depth Surface 当前从 Vector Depth EXR 的 RGB 采样 Camera XYZ，在 `Set Position` 中把 Cutout 基础网格投影为透视表面，再生成 Thickness 并执行 Smooth。相邻像素位于不同深度层时，投影会把原本相近的顶点拉开，形成跨越前后景的长边和长三角面。外层 `O Image Cutout` 的 Cleanup 只按基础网格的 Mesh Island 面积执行，无法识别仍连接在主体上的拉伸边。

旧实现曾依赖预计算的深度连续性 Field；当前 Vector Depth 已保存完整 Camera XYZ，因此可以直接在 Geometry Nodes 中比较同一条边投影前后的长度，不再增加 Server Artifact 或占用 Alpha 通道。

## Goals / Non-Goals

**Goals:**

- 直接按 Depth Surface 实际投影结果识别过度拉伸的边，并删除其关联面。
- 让判据随 `Depth Scale` 实时变化，并对不同对象尺寸使用相同的无量纲比例。
- 用默认 `0` 明确关闭剔面，保证新建结果的默认拓扑不变。
- 删除剔面后不再属于任何面的松散 Edge 与 Point。
- 保持节点主链从左到右，接口只暴露与用户结果相关的一个控制量。

**Non-Goals:**

- 不恢复 Depth EXR 中的旧 Depth Continuity 数据，也不修改 RGB 或 Validity Alpha 契约。
- 不用 Blur Attribute、曲率或模型 Validity 参与拉伸判断。
- 不为 Surface、Balloon 或 Depth Balloon 增加相同控制。
- 不新增自动 Remesh、补洞或拓扑重建。

## Decisions

### 1. 在 Point Domain 捕获投影前边长 Field

`O Image Depth Surface` 在修改顶点位置前使用 Edge Vertices 的两个 Position 计算边长，并用 Capture Attribute 以 `POINT` Domain 保存原始值。同一个未捕获的 Distance Field 直接连接 Divide，在完整 XYZ Set Position 后的 Delete Geometry 上下文中重新求值得到当前边长。

该接法与 Blender Geometry Nodes 对 Edge Vertices 距离 Field 的求值方式一致；捕获发生在 `Set Position` 之前，因此后续位置变化不会重算原始值。与在 Blender Python 中预写属性相比，节点内捕获还能让结果跟随基础几何和 Modifier 求值。

### 2. Stretch Limit 使用剩余比例阈值

拉伸判断等价于：

```text
remaining ratio = original edge length / current edge length
delete = remaining ratio < Stretch Limit
```

接口名为 **Stretch Limit**，类型为 `0–1` Factor，默认值 `0`，放在 Depth Surface 的 Options Panel。原始与当前 Edge 距离 Field 都适配到 Point Domain；值越大，清理越严格。所有正常值都不小于 `0`，因此默认值 `0` 自然关闭剔面，不需要额外 Boolean 分支。

不采用 Blur XYZ 的残差，因为它同时响应正常曲率、开放边界和 Mesh Detail。

### 3. 在投影后、Thickness 前删除 Point

节点以 `POINT / ALL` 执行 Delete Geometry。Edge 长度 Field 会适配到 Point Domain，删除超限位置及其相邻 Edge 和 Face，使深度断层成为开放边界。剔除发生在 Thickness 之前，因此后续加厚可以围绕最终表面边界生成侧壁；Smooth 只处理已经清理的表面。

拉伸判据直接读取 Set Position 后的几何，所以 `Depth Scale = 0` 时边长回到基础网格，不产生拉伸剔面；调整 Depth Scale 或 Stretch Limit 会实时更新拓扑。现有外层 Mesh Island Cleanup 仍在 Shape 分支前执行，不改变其绝对面积语义。

### 4. 按拓扑归属清理松散元素

第一次删除后，使用 Edge Neighbors 的 `Face Count == 0` 选择并删除纯线 Edge。随后使用 Vertex Neighbors 的 `Face Count == 0` 删除不再属于任何 Face 的 Point。两步都位于 Stretch Culling 后、Thickness 前。

只清理 Face Count 为零的元素，不删除开放边界上仍属于一个 Face 的 Edge，也不运行补洞或 Remesh。

### 5. 通过外层菜单组暴露 Depth Surface 专属输入

`O Image Depth Surface` 新增 `Stretch Limit` 输入；`O Image Cutout` 增加同名输入并只连接到 Depth Surface 子组。沿用当前 Menu Switch 的未使用输入隐藏行为，使其他三个 Shape 不显示或消费该参数。创建对象时依赖节点接口默认值 `0`，不增加 Operator Property 或 Server Job 参数。

## Risks / Trade-offs

- [阈值接近 `1` 时可能受浮点误差影响] → 默认关闭，并用明显跨过阈值的合成深度断层覆盖求值测试。
- [删除一条长边会同时删除它两侧的 Face，形成比单面判断更宽的开口] → 这是断层边界的预期行为，并以合成三角网格求值测试锁定范围。
- [极端阈值可能把表面切成多个较大岛] → 保留用户对 Stretch Limit 和现有 Cleanup 的独立控制，不自动 Remesh 或删除有面的岛。
- [Delete Geometry 后可能残留纯线或孤立点] → 顺序执行 Edge Face Count 与 Point Face Count 清理，并验证最终网格所有 Edge 和 Point 都属于至少一个 Face。
- [节点资产源码与 `.blend` 不一致] → 同步构建脚本、验证脚本、资产和真实 Blender 求值测试。

## Migration Plan

1. 为接口、比例判断、关闭语义和松散拓扑增加失败测试。
2. 更新 Cutout 节点资产构建脚本并重建、验证 `O_AnyImage.blend`。
3. 更新用户与内部文档，运行 Cutout 定向测试和全量测试。

回退时整体恢复节点构建脚本和节点资产即可；默认值为 `0`，无需迁移已有对象数据或 Depth Artifact。

## Open Questions

无。
