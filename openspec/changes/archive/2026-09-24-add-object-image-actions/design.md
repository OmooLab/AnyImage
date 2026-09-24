## Context

Remove Background 与 Upscale 当前通过 `image_edit_owner()` 支持 Image Empty 和材质 Image Texture 节点。AnyImage 创建的 Plane、Depth Plane、Relief Plane、Panorama 与 Cutout Mesh 都使用可追踪的图片材质，并写入 `anyimage_mesh_shape`；该属性目前仅承担内部来源标记，代码不依赖其中的 Shape 字符串执行业务分支。

本阶段只建立对象右键入口和目标事务。Delight、Depth/Normal 发现与 MoGe 补图留给后续独立变更。

## Goals / Non-Goals

**Goals:**

- 使用统一的 `o_image_object` 标记识别 AnyImage 创建的图片 Mesh 对象。
- 从 3D View 和 Outliner 直接对标记对象执行 Remove Background 与 Upscale。
- 明确解析对象材质中的 Color Image Texture，并沿用现有异步提交与 Undo 语义。
- 在共享 Image 或共享 Material 时只改变发起对象的显示结果。

**Non-Goals:**

- 不实现或显示 Delight。
- 不寻找 Depth、Normal，也不运行 MoGe。
- 不支持任意普通 Mesh 的材质猜测。
- 不迁移旧 `.blend` 中的 `anyimage_mesh_shape`，也不保留旧属性读取路径。

## Decisions

### 1. `o_image_object` 是统一布尔能力标记

所有 AnyImage 创建的图片 Mesh 对象写入 `object["o_image_object"] = True`，并停止写入 `anyimage_mesh_shape`。该标记覆盖 Plane、Depth Plane、Relief Plane、Panorama 与全部 Cutout Shape；它只表达“该对象可按 AnyImage 图片对象解析”，不再混合保存 Shape 类型。

对象本身已有 Modifier、节点组和材质结构表达具体几何类型，继续在自定义属性中重复 Shape 会形成第二份状态。旧标记没有运行时消费者，因此直接移除而不增加兼容层。

### 2. 菜单按标记显示，Operator 按目标有效性启用

在 `VIEW3D_MT_object_context_menu` 与 `OUTLINER_MT_object` 注册独立的对象菜单绘制函数。活动对象为 Mesh 且 `o_image_object` 为真时显示 `AnyImage` 子菜单，菜单复用现有图片操作绘制逻辑，只包含 Remove Background、Upscale 和现有 AI 设置入口。

标记决定菜单可见性；Color 目标、服务忙碌状态和 Upscale 尺寸限制继续由 Operator `poll()` 决定。普通 Mesh、Image Empty 和未标记对象不走该入口。

### 3. 对象目标只接受 AnyImage 已知材质拓扑

对象解析从活动材质槽开始，沿 Material Output 的 Surface 连接识别 AnyImage 创建的材质拓扑，并取得驱动 Color 的唯一 Image Texture。它同时覆盖普通图片材质、Depth/Relief 材质和 Panorama 的 Emission 材质。

解析不按节点位置、显示名称或“第一个 Image Texture”猜测。材质被替换、输出未连接、Color 候选不唯一或 Image 不可编辑时返回无目标，也不回退到其他编辑器上下文。

### 4. 对象事务捕获对象、材质槽、节点与 Image

对象入口创建目标时记录对象身份、材质槽、Material、Color 节点与 Image。异步结果提交前验证这些关系仍然成立；任一项被删除、替换或改绑时拒绝提交并清理结果。

Image 独占时沿用现有原位内容替换。Image 被其他节点使用时，仅为当前 Color 节点绑定独立结果。Material 被其他对象共享时，先为发起对象复制当前材质槽，再在副本中定位对应 Color 节点并提交，避免同一节点变更影响其他对象。

### 5. 现有操作不增加对象专用执行路径

Remove Background 与 Upscale 继续使用各自现有 Operator、模型配置、输入限制和服务端 Job。通用图片目标层增加对象来源后，两项操作无需复制请求与响应逻辑。对象入口成功后仍只产生一个现有 Undo 步骤。

## Risks / Trade-offs

- [旧场景对象只有旧标记] → 按项目约定不保留兼容读取；仅新生成对象显示菜单，并在变更说明中标明破坏性调整。
- [用户修改了材质节点] → 只识别已知 AnyImage 拓扑；解析失败时禁用操作，不猜测图片。
- [Material 同时被多个对象使用] → 提交前复制发起对象的材质槽并在副本中更新 Color 节点。
- [异步期间对象或材质变化] → 提交前验证完整目标关系，失败时保持场景现状并释放结果。
- [菜单与 Image Empty 菜单冲突] → 对象绘制函数只接受带标记 Mesh，现有 Image Empty 入口保持独立。
