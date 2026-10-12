## Context

`supports_mesh_baking()` 当前验证完整修改器栈；`materialize_mesh_and_textures()` 对完整栈求值；`BakeMesh.execute()` 成功后调用 `obj.modifiers.clear()`。三处需要统一使用同一个烘焙边界。

Cutout 创建流程产生 `O Image Cutout`、`O Image Depth Cutout` 或 `O Image Depth Cutout → O Image Cutout Symmetry`。Depth Symmetry 的首个节点始终是 Depth Cutout。

## Goals

让 Bake Mesh 固化栈开头的 AnyImage 生成部分，保留用户追加的修改器及其设置，维持已有贴图事务和 Undo/Redo。

## Decisions

### 统一解析烘焙前缀

在 `bake_mesh` 包内用一个解析入口返回待烘焙修改器序列。`poll()`、材质校验、网格求值和 Operator 提交都使用该结果，单区判断使用前缀首项。

首项必须是受支持且同时启用视口、渲染的 Geometry Nodes 修改器：

| 首项节点组 | 烘焙范围 |
| --- | --- |
| `O Image Plane`、`O Image Depth Plane`、`O Image Relief Plane`、`O Image Depth Panorama` | 首项 |
| `O Image Cutout` | 首项 |
| `O Image Depth Cutout` | 首项；紧接 `O Image Cutout Symmetry` 时一并烘焙 |

紧接 Depth Cutout 的 Symmetry 属于生成部分，同样检查启用状态。前缀结束后的修改器作为后续处理保留，允许任意类型、节点组和启用状态。首项之前存在其他修改器时不成立；这使烘焙范围始终是一个明确、连续的前缀。

### 后续修改器原位保留

生成静态 Mesh 时，在主线程临时关闭后续修改器的 `show_viewport`，刷新依赖图，再通过现有 `new_from_object(..., preserve_all_data_layers=True)` 求值前缀。视口开关上的驱动器同时临时静音，保证依赖图求值期间关闭状态成立。用 `try/finally` 恢复每项原始视口状态、驱动器静音状态并刷新对象数据；`show_render` 等其他设置保持原值。

临时状态只覆盖网格求值阶段。后续修改器继续留在原对象上，实例、节点组引用、自定义输入、名称和动画数据保留，避免重建时遗漏 Blender 的修改器数据。

### 成功提交只移除前缀

贴图及 Mesh 准备完成后，替换 `obj.data`，逐项移除待烘焙修改器，更新对象。后续修改器按原相对顺序作用于静态 Mesh。

Depth Image 候选仅从待烘焙修改器收集，移除后仍按实际 users 数清理。沿用共享材质和图片隔离规则，成功时移除 `o_image_object` 及现有协议属性。

例如 `O Image Depth Cutout → O Image Cutout Symmetry → Smooth → 用户 Geometry Nodes` 完成后保留 `Smooth → 用户 Geometry Nodes`；静态 Mesh 是对称输出，后续操作继续实时求值。

### 保持失败恢复和 Undo/Redo

原 Mesh 和完整栈在准备成功前保留。任何准备阶段异常都恢复后续修改器的临时状态，沿用图片／材质回滚并释放临时资源。成功操作继续使用 Blender 的 `UNDO`，覆盖前缀移除、静态 Mesh、图片变化和对象能力标记。

## Risks / Trade-offs

- 临时禁用后依赖图仍可能保留旧求值结果 → 在关闭和恢复阶段更新对象，测试静态 Mesh 明确排除后续变形，最终求值包含一次后续变形。
- 用户 Geometry Nodes 可能读取 AnyImage 协议属性或依赖原始 UV 布局 → 后续节点接收 Bake 后的静态 Mesh、最终 `UVMap` 和材质；验证标准 UV 与用户属性保留。AnyImage 协议属性继续按已有生命周期清理。
- 修改器设置可能包含图片引用、驱动和复杂 Geometry Nodes 输入 → 原位保留实例，覆盖引用、输入、动画关联与启用状态测试，并验证仍被引用的 Depth Image 存活。
- 法线贴图固化与后续几何变形会共同决定最终外观 → 法线按前缀几何烘焙，使用代表性 Smooth 和 Geometry Nodes 场景验证最终几何和渲染。
