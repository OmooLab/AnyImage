## Context

`O_AnyImage` 的顶点位置平滑只有两条路径：`tools/nodes/common/smoothing.py` 的 `expand_smooth()` 供三个深度节点组的边界平滑使用，`tools/nodes/groups/image_cutout_symmetry.py` 的 `_apply_planar_relax()` 供 Fill 与 Seam 使用。

两者用同一套 Blur Attribute 结构，但形态不同：`expand_smooth()` 用 Repeat 逐轮把顶点位置混向「内部模糊结果，边界点改用边界条带模糊结果」，并乘上作用于切边带的影响场；`_apply_planar_relax()` 一次性做 N 次模糊，再取平面内分量、乘固定 0.5 与轮廓/切缝的两圈 falloff 后作为位移。前者已经等于 OmooNodes `O Smooth` 的 `Pin Boundary = 1`，但两者都没有 `Pin Sharp`，`_apply_planar_relax()` 也没有边界条带分支，轮廓会被内部模糊往里拖。

参考实现 `O Smooth`（OmooNodes 的 `O_Essentials_GeometryNodes.blend`）把两个 pin 表达为输入：`Pin Boundary` 在「内部模糊结果」与「边界条带自身 0.5 权重模糊结果」之间选择边界点目标；`Pin Sharp` 用 `|Blur(Normal, 10)|` 压低尖锐处的平滑权重。本变更把这两个输入固定为 1，并让所有几何平滑共用这一层。

两处的受力点性质不同。深度三组与 Seam 的受力点是真正的网格边界（Split 切边、原图边框、对称平面的切缝），轮廓是否被拖拽、锐边是否被抹平都直接影响外形。Fill 则作用在 front 表面与它挤出的侧壁之间的衔接带：壁在平滑之后才挤出，衔接处不是网格边界，两个 pin 在这里没有对象，用力方向反而是把这一带放松成圆滑过渡。

## Goals / Non-Goals

**Goals:**

- 真正位于网格边界的平滑固定带上 `Pin Sharp = 1` 与 `Pin Boundary = 1`，且不新增 modifier 接口。
- Fill 作为衔接带的普通平滑，作用范围比原先的两圈更宽。
- 深度三组与 Cutout Symmetry 的平滑共用同一个构建函数，站点只提供作用范围、权重与是否 pin。
- 保持作用范围的渐变语义与 Cutout 中轮廓、切边的权重差异。

**Non-Goals:**

- 不把 pin 应用到法线平滑、深度模糊、掩码与统计模糊等属性平滑。
- 不改变作用范围的宽度、渐变形态与迭代次数的公开含义。
- 不保留旧的平面内偏移平滑路径或兼容输入。

## Decisions

1. **把平滑拆成作用范围层与 pin 层。** 作用范围层继续回答「哪些顶点允许动、每轮动多少」，由调用方传入 region 与 weight 字段；pin 层回答「边界点用哪个目标」「锐处权重要不要压低」，由共享实现的 `pin_boundary` 与 `pin_sharp` 分别生成。相比把 pin 混进各站点的影响场，这样 Cutout 的轮廓 0.1 与切边 1.0 权重、Seam 与 Fill 的 falloff 都能原样保留。
2. **共享函数放在 `common/smoothing.py`。** 签名收敛为几何、迭代次数、region、weight、可移动分量与两个 pin 开关：Repeat 每轮按 `weight × region` 把位置混向目标，`pin_boundary` 决定边界点是否改用边界条带模糊结果，`pin_sharp` 决定是否乘锐度系数。`expand_smooth()` 不再保留独立实现，`boundary_smoothing.py` 只负责构造 Cutout 的 region 与 weight。
3. **边界条带分支与 O Smooth 完全一致。** `Separate Geometry` 取出边界点，对位置做权重 0.5 的一步 Blur，再用 `Sample Nearest` 的索引取回，边界点目标改为该结果。边界顶点仍会沿边界移动，只避免被内部平滑拖拽收缩，因此不需要额外参数表达「冻结边界」。
4. **锐度权重与 O Smooth 一致。** 对 `Normal` 做 10 次权重为 1 的 Blur，取长度作为逐点系数乘进权重。备选方案是用面夹角或锐边属性判断，但那需要额外的拓扑判定与属性传递；法线相干度直接复用参考实现，判定成本低且没有新增数据。
5. **迭代机制统一为 Repeat。** Symmetry 现在是一次 N 次 Blur 再乘比例的偏移，改为与深度三组相同的逐轮混合；这样同一份实现即可覆盖两处，且 region 与 weight 在每轮都参与，收敛路径可预期。
6. **用可移动分量保留对称平面约束。** Symmetry 的前表面折叠在对称平面上，位移若离开平面会破坏镜像焊接，因此共享函数允许调用方传入分量掩码；Fill 与 Seam 传平面内分量，深度三组保持默认全轴。该掩码表达的是几何约束，不是平滑语义。
7. **删除旧路径而不是并存。** `_apply_planar_relax()` 与其一次性模糊的偏移实现直接移除，符合项目不保留转发函数与兼容层的要求。
8. **Fill 拆开两个 pin，并把衔接带锚在完整边界。** 衔接处不是网格边界，`Pin Boundary` 在这里没有判断对象；但 `Pin Sharp` 仍然有效，衔接带内的尖锐处应当少动，因此两个 pin 拆成独立开关，Fill 传 `pin_boundary=False` 并保留 `pin_sharp=True`。锚点由「界外轮廓」改为 front 的完整边界带（界外轮廓 + 对称面上的切缝）：只锚在界外轮廓时，对称轴上的点一旦超出渐变圈数就完全不受力，衔接在轴处断开。渐变宽度仍由 `FILL_SMOOTH_RINGS = 4` 单点控制。

## Risks / Trade-offs

- [轮廓行为变化：Seam 与深度三组的轮廓不再被内部模糊拖动] → 这是本变更的目标；用行为测试锁定「范围外顶点不动」「轮廓点位移只来自边界条带分支」「Cutout 轮廓与切边权重差异保留」。
- [Fill 范围更宽且覆盖对称轴，front 靠近边界的一段会被邻域平均拉动] → 这正是衔接圆化的目标；受力范围由 `FILL_SMOOTH_RINGS` 控制，测试锁定第三圈仍受力、配置圈数之外保持原位，对称轴上的点参与松弛。
- [Pin Sharp 会压低 Split 台阶处的平滑权重，与去台阶目标相抵] → 已在参考实现中验证细节保留更好，保留该行为；台阶处理强度仍由 `Boundary Smooth` 迭代次数和切边完整权重控制。
- [统一迭代机制改变 Symmetry 的收敛路径] → 保留现有对称性与闭合测试，并新增 pin 覆盖，确认镜像焊接与闭合性不被破坏。
- [节点数量与求值成本增加] → 深度三组本来已有边界分支，只新增法线模糊；Symmetry 新增边界分支与 Repeat。共享实现避免了两套重复复杂度。
