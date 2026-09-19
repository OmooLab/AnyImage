## Context

`O Image Depth Panorama` 现在的 Depth Mask 是一个开关包住 Delete Geometry：面中心的 mask 采样低于 Mask Threshold 就删面。被删的面在之后的链路里不复存在，Depth Mask 关闭时只能让无效面按点回退到 `Dome Radius`，整片网格仍以同一个连通体走 Depth Split 与边界平滑。

球面网格在删除后出现的自由边界就是 mask 切口，切口深度规则、边界带深度模糊与位置平滑都建立在「切口是一段自由边界」之上。Separate Geometry 可以把同一个 mask 判定变成两条独立分支：低 mask 面与其余面各自成网格，那么关闭开关时就有条件把两者分开处理。

## Goals / Non-Goals

**Goals:**

- 用 Separate Geometry（Face 域）替代 Panorama 上的 Delete Geometry，低 mask 区域成为可继续处理的几何。
- Depth Mask 打开时输出与按面删除等价的结果；关闭时两个区域各按自己的方式位移后合并。
- 维持切口规则、Depth Split、Depth Scale、UV 与材质协议的既有职责。

**Non-Goals:**

- 不改动 `O Image Depth Plane` 的 Depth Mask 删除行为，也不改动 `validity.delete_invalid_faces`。
- 不新增或改名接口输入，不改 Mask Threshold、Dome Radius、Depth Scale、Depth Split 的语义与默认值。
- 不引入跨分支的焊接、合并或平均。

## Decisions

### 分面判定沿用面心比较

Separate Geometry 的 `Selection` 接当前的 `invalid`（面中心采样 `< Mask Threshold`），`Inverted` 即保留面。判定仍只做一次比较，切口轮廓仍落在面中心上，低 mask 区域就是被旧逻辑删掉的那批面。

### 开关切换的是「低 mask 区域是否并入」

高 mask 分支照原链路处理：`split_depth_surface` → `build_surface_camera` → 深度边界模糊 → 半径 `Dome Radius + Depth Scale × (d − Dome Radius)` → Set Position → 清理 `_o_*` → 切口带位置平滑。低 mask 分支先把单位球面上的位置乘 `Dome Radius` 落到 dome 球面，再走同一套切口带位置平滑；它不参与 Depth Split，也不参与深度边界模糊（半径与采样深度无关）。

最后 `Join Geometry` 合并两条已各自定形的分支，再一起过 Flip Faces、Shade Smooth 与材质槽继承。Depth Mask 开关用一个 Geometry 类型的 Switch 实现：打开时取高 mask 分支，关断时取无 mask 一侧的结果；后者再按「Depth Scale 为 0」分一次，直接取整球。两条分支都要先算出来才能让开关只选结果，Join 因此总是执行；相比「再删一次低 mask 分支来制造空几何」，这条路径少一个节点，且把开关语义放在输出侧。

**为什么不是整片网格加回退**：旧做法把面域判定插值到点域来写回退距离，接缝点的归属取决于相邻面插值，切口处既可能拿到 dome 也可能拿到采样深度；分面后每个点只属于一个区域，判定没有插值空间。

### 关闭开关时不再保留逐位不变的契约

分面后接缝两侧各自持有自己的顶点，合并不会焊接：接缝是两条分支的自由边界，和打开开关时的切口一样。这是分面结构的直接结果，也是有意的取舍，取代 `unify-mask-cut-depth` 里「Depth Mask 关闭时几何逐位不变」的场景。

### 两侧边界都交给 Boundary Smooth

切口带平滑让接缝两侧的过渡一致：高 mask 分支平滑切口带，低 mask 分支平滑自己的自由边界，两者都发生在合并之前，各自只看到自己的拓扑。合并之后再平滑会把两条分支拼成的一张网格当成一个整体，接缝两侧互相牵动，所以平滑必须留在合并前。低 mask 分支不传 Depth Split 边界，它的自由边界全部按轮廓处理。

### Depth Scale 为 0 且关闭 Depth Mask 时旁路

Depth Scale 为 0 时整张表面都落在 dome 球面，再分面只会得到两批共面但接缝顶点不共享的网格，白白引入切口与缝隙；Depth Mask 又关断了排除，分面没有任何输出差异。这一组合因此旁路分面与全部后续处理，直接把球面乘 `Dome Radius` 输出，得到无切分的完整球面。

Depth Mask 打开时不能旁路：低 mask 区域仍要按 mask 排除。旁路条件因此是「Depth Scale 不大于 0」与「Depth Mask 关闭」的合取。

## Risks / Trade-offs

- Separate Geometry 的 `Invert` 与 Delete Geometry 在索引顺序上可能不同 → 断言按坐标、面集合与半径比较，不比较索引编号。
- 关闭开关时接缝顶点复制会让输出的顶点数多于旧的整片网格 → 测试改为按分支语义断言（面数、分区域半径、接缝无共享点）；Depth Scale 为 0 的旁路单独断言封闭整球。
- 合并结果在接缝处暴露两条自由边，材质与法线在接缝上不连续 → 这是关闭 Depth Mask 时的既有语义（无效区本就与有效区差一个量级），保持翻转与 Shade Smooth 作用在合并后的整体上。
- 低 mask 分支在 Depth Scale 为 0 时与高 mask 分支重叠在同一球面 → 不焊接，保持两条分支的独立边界，行为与打开开关时的一致。
