## Why

Cutout 的基础 Mesh 目前先被转换到 YZ 平面，以局部 `-X` 作为正面法线，再由 `O Image Cutout` Modifier 转回源 Image Empty 的 XY 平面。未求值或未复用该 Modifier 时，基础面片朝向因此与原图不一致，也让 Cutout 与其他图片 Geometry Nodes 使用两套轴向约定。

## What Changes

- 四种 Cutout Shape 统一在局部 XY 平面建模，以局部 `-Z` 表示从图片平面向内的方向；基础 Mesh、节点输入和默认 `-Z` 求值结果共享同一坐标约定。
- Surface、Balloon、Depth Balloon 与 Depth Surface 中所有厚度、鼓起、深度投影和相关向量运算由 X 轴迁移到 Z 轴。
- 保留 Cutout 工具与 `O Image Cutout` 的 **Inward Axis** 选项；`-Z` 继续作为默认输出，选择 `+X` 时由外层节点组和对象矩阵从原生 Z 轴结果执行配对转换。
- Depth Surface 的 Object Space Normal 默认按 Z 轴对象空间生成；仅在选择 `+X` 输出时转换到对应对象空间。
- **BREAKING（Shape 子节点内部坐标）**：`O Image Surface`、`O Image Balloon`、`O Image Depth Balloon` 与 `O Image Depth Surface` 的原生输入和输出从 X 轴约定改为 Z 轴约定，不提供子组级旧坐标兼容层。
- 重建并验证节点资产，确保 Cutout 与既有 `O Mesh Plane`、`O Image Depth Plane` 均遵循 Z 轴图片几何约定。

## Capabilities

### New Capabilities

- `cutout-axis-convention`: 规定 Cutout 基础 Mesh与四种 Shape Geometry Nodes 的原生局部 Z 轴语义，以及 `Inward Axis` 对输出几何、对象放置和 Object Space Normal 的配对转换。

### Modified Capabilities

无。

## Impact

- 影响 Cutout BaseShape 坐标、对象创建与放置，以及既有 `Inward Axis` 参数的节点转换方向。
- 影响 `O Image Cutout` 及四个 Shape 子节点组的构建脚本、内部坐标约定、验证脚本与发布资产 `O_AnyImage.blend`；外层 `Inward Axis` 接口和值保持不变。
- 影响 Depth Surface Object Space Normal 的坐标转换及相关 Server、Blender 和真实节点求值测试。
- 不改变 Cutout 的选区、网格密度、UV、材质、Job 请求或 Depth/Normal 文件格式，也不新增依赖。
