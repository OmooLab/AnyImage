## Why

AnyImage 生成的 Mesh 对象已经具有明确的图片材质，但 Remove Background 和 Upscale 只能从 Image Empty 或 Image Texture 节点进入。先建立对象级图片入口，可让用户直接对选中的 AnyImage 图片对象执行现有操作，并为后续 Delight 保留清晰的接入位置。

## What Changes

- **BREAKING**：将内部对象标记 `anyimage_mesh_shape` 替换为布尔标记 `o_image_object`；所有 AnyImage 生成的图片 Mesh 对象统一写入该标记，不保留旧属性或兼容读取。
- 在 3D View 与 Outliner 中为带有 `o_image_object` 标记的对象提供 `AnyImage` 右键菜单，包含 Remove Background 和 Upscale。
- 增加对象图片目标解析，从 AnyImage 创建的材质连接中取得唯一 Color Image Texture；目标无效时不回退到 Image Empty 或 Shader Editor 节点。
- 复用现有图片编辑事务、AI 配置、异步任务和 Undo 行为；操作只更新当前对象对应的 Color 图片目标。
- 本阶段不增加 Delight 菜单项、贴图发现、Depth/Normal 生成或去光算法。

## Capabilities

### New Capabilities

- `object-image-actions`: 定义 AnyImage 图片对象标记、对象右键菜单、Color 目标解析和现有图片操作的对象级提交行为。

### Modified Capabilities

无。

## Impact

- 影响 Plane、Depth Plane、Relief Plane、Panorama 与 Cutout 对象创建代码中的内部标记，以及对象菜单、图片目标解析、注册和相关测试。
- 复用现有 Remove Background、Upscale、Image Edit Target 与服务端 Job，不新增模型、依赖或服务端处理类型。
- 旧 `.blend` 中仅带 `anyimage_mesh_shape` 的对象不会获得新菜单；重新生成的对象使用 `o_image_object`。
