## Context

Convert to Plane 当前使用 Image Empty 的局部显示边界直接创建 Mesh，再复制源对象矩阵。非居中的 `empty_image_offset` 因此被写入顶点坐标，结果外观位置正确，但对象原点不在面中心。

`O Image Depth Plane` 当前先让 `O Mesh Plane` 生成零厚度网格，再进行一次挤出并移动前侧。该拓扑没有沿厚度方向的中间环；运行时又把默认 `Subdivide` 写为 `0`，深度图通常没有足够顶点形成地形。它还使用与 Cutout 不一致的 `Depth Amount`、`Reference Depth` 和重复的 `Material` 输入。

对象创建代码已经把图像材质追加到 Mesh 第 0 个材质槽。`O Image Cutout` 直接依赖该槽，而 `O Mesh Plane` 额外通过 `Material` socket 和 Set Material 节点重复同一职责。

Depth Plane Job 与 Cutout Job 已共同调用 `generate_moge2_artifacts()`，但 Depth Plane 当前只请求 Z Depth。共享生成层能够从同一个 MoGe-2 `GeometryFrame` 同时写出 Z Depth 与 Tangent Normal，因此不需要第二次模型推理。

## Goals / Non-Goals

**Goals:**

- 让普通 Plane 和 Depth Plane 以面中心为对象原点，并严格保留原显示矩形的世界空间位置。
- 把 Depth Plane 建模为一面置换、背面固定、侧壁分层渐变的地形体块。
- 统一 Depth Plane 与 Cutout 的 `Depth Scale`、`Base Plane Depth` 术语。
- 让 Mesh 材质槽承担材质归属，并让纯生成的 Plane 几何保留输入 Mesh 的材质集合。
- 让 Depth Plane 的几何置换与材质法线共享一次 MoGe-2 预测。
- 用节点接口、求值几何和世界空间位置测试固定行为。

**Non-Goals:**

- 不修改 MoGe-2 推理、Z Depth EXR、Validity Alpha 或 `depth.json` 协议。
- 不按每张深度图归一化位移，也不让 `Thickness` 限制正向地形高度。
- 不增加侧壁环数量、插值曲线或位移方向等新控制项。
- 不修改 Cutout 的几何或材质行为。
- 不合并 Cutout 与 Depth Plane 的顶层 Job 编排。

## Decisions

### 1. 通过局部重心与矩阵补偿移动对象原点

设 Image Empty 局部显示边界中心为 `C`、原矩阵为 `M`。新 Mesh 使用 `P - C` 作为顶点坐标，新对象矩阵使用 `M × Translation(C)`，因此：

```text
(M × Translation(C)) × (P - C) = M × P
```

普通 Plane 和 Depth Plane 共用同一套居中网格与放置计算，UV 仍覆盖 `0–1`。该方法不调用依赖当前选择和 Context 的 Origin Operator，也能正确保留旋转、非均匀缩放和 Image Empty 偏移。

不选择先创建对象再调用 `origin_set`，因为该 Operator 依赖 Blender Context，并会把稳定的坐标变换变成隐式场景操作。

### 2. 纯生成几何显式保留 Mesh 材质集合

从 `O Mesh Plane` 删除 `Material` interface socket；`O Image Depth Plane` 同步删除对应 socket 与转发。运行时继续在添加 Modifier 前执行 `mesh.materials.append(material)`。

Mesh Grid 和 Mesh Cube 是完全生成的几何，仅设置材质索引 `0` 不会自动保留输入 Mesh 的 Material Set。因此 `O Mesh Plane` 先在输入几何上捕获恒真匿名属性，再把输入几何与生成几何临时 Join，统一设为材质索引 `0`，最后按捕获属性删除全部输入点。输出只剩生成几何，但仍携带输入 Mesh 的材质集合。验证脚本将求值普通 Plane、厚度体块和 Depth Plane，检查求值 Mesh 保留第 `0` 个材质槽且所有面使用索引 `0`。

不保留隐藏 `Material` socket，因为它仍会形成第二条材质来源，并允许 Modifier 输入与对象材质槽漂移。

### 3. Depth Plane 直接复用 O Mesh Plane 的厚度拓扑

`O Image Depth Plane` 将输入 Geometry、`Subdivide` 和 `Thickness` 交给 `O Mesh Plane`。`O Mesh Plane` 的 Cube 路径已经按表面网格步长计算厚度方向分段；该计算增加最少侧壁分段，保证固定底面与可变面之间存在中间环，但不增加公开控制项。

`O Mesh Plane` 的体块以原平面为中心，Depth Plane 在内部沿局部 Z 平移 `Thickness / 2`，得到：

```text
固定底面   z = 0
未置换可变面 z = Thickness
```

`Thickness = 0` 时保留单张置换表面，不生成重叠的背面或侧壁。

不继续使用单次 Extrude，因为它只生成跨越完整厚度的侧面，无法表达逐环渐变；也不复制一套 Grid/Cube 构建逻辑，避免与 `O Mesh Plane` 的纵横比分段和 UV 规则漂移。

### 4. 使用同一个标量场驱动正面和侧壁环

每个 XY 位置从 `z-depth.exr` 采样 Z Depth。隐藏的 `Uniform Scale` 把相机深度转换为对象局部距离，完整正面位移为：

```text
depth = sampled_z × Uniform Scale
full_offset = (Base Plane Depth - depth) × Depth Scale
```

这使较近深度向局部正 Z 突出，较远深度向固定底面内缩，等于 `Base Plane Depth` 时位移为零。连续 Depth RGB 在 Validity 边界仍被采样，不用 Alpha 删除点，与当前 Artifact 协议保持一致。

体块顶点以未置换位置计算层权重：

```text
layer_weight = clamp(z / Thickness, 0, 1)
final_z = z + safe_full_offset × layer_weight
```

固定底面权重为 `0`，可变面为 `1`，中间环线性递增。线性插值比 Smooth Step 更直接地表达各层置换比例，也让截面顺序容易验证。

### 5. 负向位移限幅，正向位移保持完整

`safe_full_offset` 的下限设为略大于 `-Thickness`。因为所有层使用同一限幅结果乘以单调层权重，侧壁环不会反序，可变面也不会与固定底面重合。

正向位移不钳制。`Thickness` 表示固定底面到未置换可变面的基础厚度；固定底面始终停在原图片平面，`Depth Scale = 0` 时实际厚度恰好等于 `Thickness`，启用正向置换后最终包围盒可以更高。

不把位移归一化到固定包围盒，因为这会让相同 `Depth Scale` 在不同图片上产生不同物理尺度，并破坏固定底面、基础厚度和自由 Depth Scale 的独立语义。

### 6. 一次性替换节点接口与默认值

`Depth Amount` 直接改为 `Depth Scale`，`Reference Depth` 直接改为 `Base Plane Depth`，不添加旧名称转发。创建 Depth Plane 时继续从 Metadata 初始化基础深度与 Uniform Scale，并将 Depth Plane 的 `Subdivide` 默认值设为 `6`；普通 Plane 的默认细分保持 `0`。

节点资产、Modifier 输入设置、验证、测试和文档在同一次变更中更新并重建，不保留旧 `.blend` 接口。

### 7. 一次预测同时生成几何深度与材质法线

Depth Plane 顶层 Job 继续负责完整图片的颜色复制和结果协议，并调用共享的 `generate_moge2_artifacts()`，同时传入：

```text
depth_mode = Z
normal_mode = TANGENT
```

共享生成层只执行一次 MoGe-2 inference，并从同一个 `GeometryFrame` 写出 `z-depth.exr`、`depth.json` 和 `tangent-normal.png`。Cutout 顶层 Job 仍保留 Selection 裁切、可选 BEN2 Refine 和自身结果编排；两条工作流只共享与图片选择无关的 MoGe-2 Artifact 生成层，不把 Cutout 分支引入 Depth Plane。

Blender 响应阶段使用现有 Normal 图片加载入口把 `tangent-normal.png` 设为 Non-Color 并 Pack，再以 `normal_space="TANGENT"` 和 `ior=1.2` 传给 `create_image_material()`，使 Depth Plane 与 Cutout 使用相同的 Principled IOR。Normal Map 只参与材质着色，`z-depth.exr` 继续单独驱动 Geometry Nodes 置换；任一步失败时清理尚未被数据块使用的 Depth 与 Normal 图片。

## Risks / Trade-offs

- [高默认细分与厚度环会增加求值几何量] → 继续使用 `O Mesh Plane` 的纵横比自适应分段，并让用户通过现有 `Subdivide` 降低精度。
- [极端负向位移会形成非常薄的楔形侧壁] → 在固定底面前保留小间隙，并用求值测试检查层顺序和非穿透。
- [删除 Material socket 后纯生成几何会丢失 Material Set] → 临时 Join 带匿名标记的输入几何，设置索引后删除输入点，并对普通 Plane、厚度体块、Depth Plane 和剪贴板 Plane 做真实 Blender 求值。
- [Depth 与 Normal 分开生成会重复执行 MoGe-2] → 由共享 Artifact 生成层从同一个 `GeometryFrame` 写出两类文件，并测试 inference 只调用一次。
- [Tangent Normal 可能未进入最终材质或使用错误色彩空间] → 检查图片为 Non-Color、已 Pack，材质 Normal Texture 使用 Tangent Space 且连接到现有 `O Image Layer` 输入。
- [移动原点可能影响依赖旧局部坐标的外部脚本] → 这是预期的对象语义修正；世界空间几何保持不变，不提供兼容路径。
- [节点资产文档与当前源码已有少量名称漂移] → 在本次变更中按最终接口同步更正对应 Plane 文档，不扩展到无关主题。

## Migration Plan

1. 先修改中心原点的 Mesh 与对象矩阵计算，并固定普通 Plane、Depth Plane 的世界空间回归测试。
2. 删除 Plane 节点组的材质输入和运行时 Modifier 赋值，增加第 0 材质槽的求值验证。
3. 重建 Depth Plane 节点图、接口名称、默认细分和负向限幅测试。
4. 扩展 Depth Plane Job，让一次 MoGe-2 预测同时生成 Z Depth 与 Tangent Normal，并把 Normal 接入材质。
5. 重建并验证 `O_AnyImage.blend`，运行完整测试，再同步 Plane 与节点资产内部文档。

回退必须同时回退节点构建脚本、发布 `.blend`、运行时输入名称和对应测试，避免节点接口与 Python 写入不一致。

## Open Questions

无。
