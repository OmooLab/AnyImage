## Context

`O Image Cutout` 负责普通 Surface/Balloon，`O Image Depth Cutout` 负责深度投影后的 Balloon/Shell。二者共同消费 Cutout 基础网格和 `o_balloon`，并在输出后进入材质与法线阶段。

当前 Depth Cutout 从源码构建会生成约 441 个节点、587 条连线，其中包含 13 个 Blur Attribute、12 个 Sample Index，以及多处针对同一拓扑重复计算的边界字段。Depth Cutout 输入已确认为三角网格，因此 `_remove_strip_faces` 中的四边面清理分支是无效构建路径。普通 Cutout 和 Depth Cutout 在零厚度时仍会先生成厚度几何，再由 `_remove_zero_thickness` 选择原表面。

临时属性目前使用 `.o_anyimage_depth_cut`，通过 `remove_attributes` 按具体名称条件删除；测试和资产检查仍保留 `.o_anyimage_original_boundary` 的旧名称。公开协议属性 `o_balloon`、`o_normal_reduction` 等需要继续保留。

## Goals / Non-Goals

**Goals:**

- 在保持两个节点组公开输入、输出几何和视觉结果不变的前提下，减少 Depth Cutout 的重复节点与求值。
- 按拓扑阶段复用 projection 后的 outline 边界字段。
- 用共享的低频场推导中心场，减少一次 256 次邻域平滑。
- Depth Cutout 仅构建三角形 strip 清理路径。
- 厚度为零时提前返回单层表面，避免先生成壳体。
- 将内部临时属性统一改为 `_o_` 前缀，公开保留属性保持 `o_` 前缀，并用 Wildcard 一次性清理内部属性。

**Non-Goals:**

- 不改变 Balloon 的背面算法、平滑次数、圆润公式或法线方向。
- 不改变 Cutout 的 Operator、Job、材质协议或公开属性语义。
- 不重排节点布局；布局优化只在必要的最小范围内跟随代码路径调整。
- 不构建文档或打包扩展。

## Decisions

### 1. 投影后只计算一次 outline 字段

`_build_depth_surface` 在 `remove_boundary_triangles` 之后、`project_depth_surface` 之前已经计算 outline。投影只改变位置，不改变拓扑，因此同一个 POINT/BOOLEAN 字段在投影后仍然有效。

将该字段作为参数传给 `build_volume_fields`、`original_boundary_field` 和 `smooth_cut_boundary`，由这些函数复用，而不是各自重新创建 `edge_boundary_field`。

备选方案是继续保留局部字段，可读性更高但会重复创建多组 Edge Neighbors、Vertex Neighbors 和域转换。本变更选择显式传递，因为高密度网格下这些重复查询是可见成本。

### 2. 用共享低频场推导中心场

`build_volume_fields` 当前计算：

```text
seed = depth - profile
center = blur(seed, interior, 256)
```

`build_front_fields` 随后计算：

```text
depth_slow = blur(depth, interior, 256)
profile_slow = blur(profile, interior, 256)
```

三次 Blur 使用相同权重和迭代次数。由于邻域加权是线性的：

```text
center = depth_slow - profile_slow
```

因此重构为先计算 `depth_slow` 和 `profile_slow`，再推导 `center`，不再单独执行 center blur。这样保留原有平滑语义，同时移除一次 256 次 Blur。

### 3. Depth Cutout 使用三角形专用清理路径

将 `_remove_strip_faces` 的构建逻辑拆成 Python 层可选择的 triangle / quad 路径。`split_depth_surface` 增加显式构建参数或提供三角形专用辅助函数；Depth Cutout 调用 triangle-only 版本，Depth Plane 与 Panorama 继续使用现有 quad 路径。

Depth Cutout 输入已确认为三角网格，因此不保留运行时分支，也不构建无效的 quad 节点。

### 4. 零厚度分支提前短路

普通 Cutout 中，`_build_balloon` 和 `_build_shell` 在输入厚度低于 `1e-6` 时直接返回原几何，不再进入挤出、Repeat 或 `_set_layer_y`。

Depth Cutout 保留投影面作为零厚度结果；只有选中厚度大于 `1e-6` 时才执行 `thicken_depth_surface` 和后续字段采样、壳体位置调整。

使用 GeometryNodeSwitch 而非 Python 分支，是因为厚度是运行时输入。实现时验证 Blender 的惰性求值，确保未选择分支不会被展开。

### 5. 内部属性使用 `_o_` 前缀，公开属性保持 `o_`

内部属性定义集中到明确常量，例如将 `CUT_ATTRIBUTE` 从 `.o_anyimage_depth_cut` 改为 `_o_anyimage_depth_cut`。其他仅在本节点组生命周期内使用的临时属性也使用 `_o_` 前缀。

公开协议属性保持 `o_` 前缀，包括但不限于：

- `o_balloon`
- `o_normal_reduction`
- `o_depth_scale`
- `o_depth_rotation`
- `o_depth_face`
- `o_depth_axis`

`remove_attributes` 或新增的 pattern 清理函数使用一个 `GeometryNodeRemoveAttribute`，`pattern_mode = "WILDCARD"`，pattern 为 `_o_*`。清理放在最终输出之前，且不再按属性逐个删除。

### 6. 保持节点组构建与资产同步

源码修改后运行 `uv run node-group build`，重建并重新加载验证 `O_AnyImage.blend`。测试覆盖节点数量或关键节点类型的变化、输出几何等价、临时属性清理和高密度网格厚度闭合。

## Risks / Trade-offs

- [边界字段跨函数传递后，某个消费者可能落在不同拓扑阶段] → 仅在同一投影后拓扑内传递；每个阶段在进入前显式确认几何未改变。
- [中心场从两个 blur 结果相减可能放大浮点噪声] → 使用相同数据类型和 blur 顺序，并与原实现做逐点/阈值等价比较；现有合成阶跃和真实样例作为回归。
- [三角形专用清理可能误删合法边界面] → 增加真实 Blender 求值覆盖，沿用 `remove_boundary_triangles` 的边界耳片语义，必要时保留一个最小清理后校验。
- [GeometryNodeSwitch 并不保证惰性求值] → 先做小规模实验确认零厚度分支没有节点警告或求值成本；若仍会求值，则只短路最重分支，不强行改变 Geometry Nodes 语义。
- [Wildcard 清理可能误删用户 `_o_*` 属性] → `_o_` 定义为节点组内部保留前缀，测试确认 `o_*`、UVMap 和普通用户属性保留。

