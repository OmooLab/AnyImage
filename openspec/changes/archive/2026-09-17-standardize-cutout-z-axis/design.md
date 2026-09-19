## Context

Cutout 的二维采样和三角化本来在源 Image Empty 的局部 XY 平面完成，`cutout_domain()` 也先生成 `(x, y, 0)`。`build_base_shape()` 随后通过 `orient_cutout_vertices()` 将顶点变为 `(0, -x, y)`，让四个 Shape 子节点沿 X 轴建模；对象矩阵再根据 **Inward Axis** 选择是否追加一次轴变换。默认 `-Z` 只有在外层 `O Image Cutout` Modifier 求值后才回到源图坐标。

这使 Mesh 数据、Shape 子组和最终对象处于不同坐标系。禁用 Modifier、读取原始 Mesh、把 Shape 子组复用到普通 XY 几何，或依赖对象局部轴的后续操作，都会看到 YZ / X 轴约定。与此同时，`O Mesh Plane` 与 `O Image Depth Plane` 已经在 XY 平面生成几何并沿 Z 轴表达厚度和深度。

Depth Surface 的 Object Space Normal 也跟随旧 `-X` 原生协议：Server 先编码 X 轴 Cutout 空间，Blender 再为默认 `-Z` 修改图片像素。轴向迁移必须同时覆盖基础 Mesh、四个节点子组、外层节点组、对象矩阵与 Normal 编码，同时保留用户选择 `-Z` 或 `+X` 输出的能力。

## Goals / Non-Goals

**Goals:**

- 让 Cutout 原始 Mesh、四个 Shape 子组和默认 `-Z` 求值结果使用源 Image Empty 的局部 XY / Z 轴。
- 让四种 Shape 的内向位移统一沿局部 `-Z`，与现有 Plane 节点的 Z 轴语义一致。
- 保留 **Inward Axis** 输出选项，让默认 `-Z` 直通原生坐标，只在选择 `+X` 时执行配对的几何、对象矩阵和 Normal 转换。
- 用 Python 单元测试、节点结构验证和真实 Blender 求值固定原始与求值几何的朝向。

**Non-Goals:**

- 不改变世界空间外观、Cutout 轮廓、UV、材质、厚度数值、Depth Scale 或 Reference Depth 的视觉语义。
- 不修改 Selection、采样密度、三角化、Job 编排或 Depth Artifact。
- 不删除或重命名现有 **Inward Axis** 接口和值，也不改变两种选项的世界空间外观。
- 不重构已经采用 Z 轴的 `O Mesh Plane` 与 `O Image Depth Plane` 主链。

## Decisions

### 1. 保留三角化得到的 XY 顶点作为 BaseShape

`build_base_shape()` 直接保存 `cutout_domain()` 产生的 `(x, y, 0)`，删除 `orient_cutout_vertices()`。逆时针 Face 顺序保持不变，因此未求值基础面的几何法线为局部 `+Z`，从图片正面观察时与源 Image Empty 一致；“向图片内部”统一定义为局部 `-Z`。

默认 `-Z` 的对象矩阵为：

```text
source_matrix × Translation(crop_center.x, crop_center.y, 0)
```

默认路径不再追加轴变换。这样原始 Mesh 顶点、Modifier 输入和默认最终结果共享同一对象空间，世界空间仍由源图矩阵和裁切中心决定。选择 `+X` 时，外层节点组将 Z 轴 Shape 结果转换到 `+X` 内向坐标，对象矩阵追加其逆变换，使两次变换在世界空间抵消。

不选择只在对象创建后 Apply Modifier，因为这会丢失非破坏性 Shape 控制，也无法让子节点组直接复用 XY 输入几何。

### 2. 将四个 Shape 子组的建模方向整体迁移到 Z

节点构建脚本中所有表达厚度或轮廓外法向的 X 分量改为 Z 分量，平面内坐标由 Y/Z 改为 X/Y。相关辅助函数按职责改名，不保留 `_x` 转发函数。四个 Shape 使用同一约定：

```text
image plane = XY
front normal = +Z
inward direction = -Z
```

Surface 的前后层、Balloon 的轮廓高度、Depth Balloon 的相对深度和 Depth Surface 的相机点投影都在这一空间内直接产生原生坐标。外层 `O Image Cutout` 继续负责 **Inward Axis** Menu Switch：`-Z` 分支直通原生结果，`+X` 分支在 Cleanup、Smooth 后执行一次 Z 到 X 的坐标转换。

不选择保留内部 X 轴后仅提前旋转输入，因为子组单独复用时仍暴露旧约定，基础 Mesh 与节点 Field 的坐标也继续不一致。

### 3. Inward Axis 只转换外层输出

保留 Scene Property、工具面板项、交互参数、Operator Property、`CutoutInwardAxis` 与节点组 **Inward Axis** socket，枚举值仍为默认 `NEGATIVE_Z` 和可选 `POSITIVE_X`。语义调整为从统一的 Z 轴原生 Shape 选择输出对象空间：

```text
-Z: geometry = native_z; object_matrix = source_matrix × crop_translation
+X: geometry = Z_TO_X × native_z; object_matrix = source_matrix × crop_translation × X_TO_Z
```

`Z_TO_X` 与 `X_TO_Z` 互为逆变换，因此两种选项仍产生相同的世界空间形状。`CUTOUT_AXIS_TO_SOURCE` 可保留并改成清楚表达 X 到 Z 的矩阵名称；不得让四个 Shape 子组依赖该矩阵或旧 X 轴输入。

不选择把选项下沉到各 Shape 子组，因为这会重新引入两套内部坐标，并让子组复用者必须理解项目专用的轴切换。

### 4. 在 Server 端编码原生 Z 轴 Object Space Normal

Depth Surface 继续请求 `normal_mode=OBJECT`，但 Object Space 输出直接采用原生 Z 轴 Cutout 空间的通道映射。中性/不可见区域编码为局部 `+Z`，与几何正面一致。默认 `-Z` 时 Blender 直接加载并 Pack 图片；选择 `+X` 时，`orient_object_normal_image()` 使用与几何 `Z_TO_X` 一致的法线矩阵转换通道。

Tangent Space Normal 的映射与其他 Shape 保持不变。虽然 Z 轴 Object Space 与 Tangent Space 在当前正交图片基面上可能具有相同的数值通道变换，两者仍保留不同的材质 Normal Space 语义与请求枚举。

不选择继续让 Artifact 固定使用旧 X 轴空间，因为默认路径仍需在 Blender 主线程复制和改写整张图片。迁移后只有显式 `+X` 选项承担这项转换成本。

### 5. 用三层验证覆盖轴向契约

- Python 几何测试检查 BaseShape 位于 `z = 0`、XY bounds 与源裁切一致、Face winding 产生 `+Z` 法线。
- 节点结构验证检查四个子组只使用 Z 轴，外层组保留 **Inward Axis** 且仅 `+X` 分支包含最终轴变换。
- Blender 求值测试以 XY Grid 直接驱动每个 Shape，检查平面内 X/Y 不被交换、Thickness/Depth 沿 `-Z`、默认原始 Mesh 与零形变求值结果朝向一致，并验证 `+X` 输出与对象矩阵组合后的世界空间结果不变。

已有 `O Mesh Plane` 与 `O Image Depth Plane` 只增加共同轴向断言，不改其实现。

## Risks / Trade-offs

- [X 到 Z 的机械迁移可能遗漏某个位置、法线或边界分量] → 按四种 Shape 分别验证包围盒、法线、厚度和 Depth 求值，并搜索遗留的 X 轴辅助函数与常量。
- [Face winding 与内向位移可能组合错误，造成背面或侧壁翻转] → 同时检查基础面、前后层和侧壁 Polygon Normal，而不只比较顶点包围盒。
- [Depth Surface Object Normal 的通道映射可能与几何轴迁移不同步] → 用已知相机法线与不可见像素验证 Z 轴编码，并分别测试默认原样加载和 `+X` 单次转换。
- [配对矩阵方向写反会让 `+X` 世界空间结果旋转] → 用非对称裁切与非单位源矩阵对比两种 Inward Axis 的世界空间顶点，而不只检查局部包围盒。
- [重建资产可能引入无关二进制差异] → 仅修改 Cutout 构建路径，运行既有节点资产验证和完整测试，不构建其他文档或发布产物。

## Migration Plan

1. 先调整 BaseShape 与对象放置，补充未求值 Mesh 和世界空间位置测试。
2. 将四个 Shape 子组从 X 轴迁移到 Z 轴，反转外层 `Inward Axis` 分支的直通/转换职责并更新结构、求值验证。
3. 保留运行时 **Inward Axis** 属性与参数链，简化默认 `-Z` 对象矩阵并为 `+X` 使用配对补偿。
4. 修改 Object Space Normal 为 Z 轴原生编码，让默认路径原样加载、`+X` 路径执行配对通道转换，并更新 Server/Blender 测试。
5. 重建并验证 `O_AnyImage.blend`，运行 Cutout 定向测试和 `uv run pytest`，同步节点资产与 Cutout 内部文档。

回退时必须一起恢复节点构建脚本、`O_AnyImage.blend`、BaseShape 坐标、对象放置和 Normal 编码，避免资产与运行时使用不同坐标系。

## Open Questions

无。
