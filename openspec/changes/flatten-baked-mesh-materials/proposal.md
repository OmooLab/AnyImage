## Why

Bake Mesh 已能固化几何和法线属性，但结果仍依赖 O Image Layer 的粗糙度、法线强度和 Bump 计算。将这些效果固化为贴图，可以让静态网格使用更直接、易编辑的标准材质节点。

## What Changes

- **BREAKING**：从 Bake Mesh 的结果材质中移除 O Image Layer 实例，以标准节点承接其全部输出连接。
- 将统一颜色后的 Roughness 与 RGB 灰度 Specular 分别固化为独立的 0–1 Non-Color PNG 贴图。
- 将 Normal Map、Normal Scale、几何属性适配和 Bump 的最终组合效果固化为一张 Tangent Normal；结果使用 Strength=1 的 Normal Map 节点。
- 支持只有 Bump、没有源 Normal 图片的材质，按需创建法线图。
- Color 不受偏好设置影响，统一为 0–1 sRGB，保留 Alpha 和 Atlas 规则；Alpha 修正用独立标准节点承接，保留其他节点、参数及连接目标。发光强度为 0 时断开 Emission Color，大于 0 时复制最终 Color 为独立 `_emissioncolor` 图片。
- 贴图节点按 Principled BSDF 输入顺序纵向排列。
- 保持修改器前缀边界、共享资源隔离、事务提交、Undo / Redo 和打包重载行为。

## Capabilities

### New Capabilities

- `baked-material-flattening`：Roughness 与含 Bump 的 Normal 固化，以及烘焙材质移除 O Image Layer 后的输出连接。

### Modified Capabilities

- `cutout-texture-materialization`：将法线强度与 Bump 烘入结果，允许新增结果贴图，并调整材质结构保留要求。
- `mesh-bake-boundaries`：按新增贴图操作校验输入，扩展节点事务和结果贴图分类。

## Impact

- 实现主要涉及 `operators/bake_mesh/materialization.py`、包内贴图与材质职责，以及相关 Blender 行为测试。
- 复用 `common` 的图片、共享资源检测和状态恢复能力；使用既有 Blender / Cycles 能力。
- 范围是 Bake Mesh 的结果材质；可编辑对象继续使用现有 O Image Layer 资产。
- 复用现有颜色归一化：inverse / HDR 线性 RGB 按通道截断到 0–4、除以 4、Gamma 0.75、编码 sRGB；普通 sRGB 和已归一化图片保持编码值。可编辑材质继续保留 inverse 颜色所需的钳制。
