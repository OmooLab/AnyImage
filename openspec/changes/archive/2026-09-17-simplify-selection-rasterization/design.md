## Context

Selection 手势当前构建带 `points`、`invert`、`fill_rule` 和 JSON 方法的 `SelectionPath`。Image Tool 默认使用 `EVEN_ODD`，Cutout 使用 `NONZERO`；两者只在自交或重复绕行时不同。产品决定统一保留同方向重叠区域，因此删除 `EVEN_ODD`，同时保留 `SelectionPath` 及其 JSON 方法，继续把路径点和反选状态作为不可分割的值。

当前栅格器已经取得 Path bounds，却仍创建整图 Mask，并对每条路径边构造“扫描行块 × 选区宽度”的二维布尔数组。实测 5120×2880、1000 点 Lasso 的完整处理约为 4.07 秒。局部 non-zero scanline 原型通过每条边只记录实际穿过扫描行的区间端点，再对每行累计一次，在 960 组路径、Invert、抗锯齿、Alpha 和 bounds 组合中与目标 non-zero 结果逐值一致，同一 5K 用例约为 0.16 秒。

Cutout Pie Menu 的按钮会启动新的 Blender Operator，普通 Python 对象不能直接跨该 RNA 边界。现有完整 Path JSON 已同时保存 Points 与 Invert，千点路径编码实测约 0.6 ms；保留 `to_json()` / `from_json()` 比拆分多个 Property 或增加 RNA Collection 更直接。

## Goals / Non-Goals

**Goals:**

- 所有 Selection 使用 non-zero winding，保留同方向重叠区域。
- 运行时传递只包含普通二维点数组和 `invert` 的精简 `SelectionPath`，删除 `fill_rule`。
- Cutout 只在 Pie Menu 到 Shape Operator 的必要边界编码一次完整 Selection Path。
- 将 Path-to-Mask 的计算量从逐边二维像素广播改为扫描行交点累计，并尽可能限制在局部画布。
- 保持现有像素中心、Invert、抗锯齿核、Alpha 阈值、空 Selection、最终 bounds 和下游输出语义。

**Non-Goals:**

- 不缓存 Blender 图片像素或 Selection，不引入令牌和全局状态。
- 不改变 Lasso 采样与简化容差，不增加 Pillow、OpenCV 或 GPU 路径。
- 不优化 Blender `image.pixels.foreach_get()`、图片写回、Pack、Cutout 网格或 AI Job。
- 不保留旧 `fill_rule` 或兼容填充分支。

## Decisions

### 1. Selection Path 只保存 Points 与 Invert

`SelectionPath` 保留为不可变 dataclass，只包含 `points: tuple[tuple[float, float], ...]` 与 `invert: bool`，以及完整值的 `to_json()` / `from_json()`。构建时继续把点规范化为有限浮点二维数组、检查至少三个点，并固定反选值。共享手势完成边界提交一个完整 `SelectionPath`，Image Tool 在同一 Operator 调用栈内直接消费它。

`invert` 决定路径内部还是外部属于 Selection，与 `points` 共同定义同一个 Selection Path。保留二者的值对象及现有序列化边界可以避免调用链漏传或错配反选状态；删除 `fill_rule` 后，该类型不再承担工具填充策略。

### 2. Cutout 序列化完整 Selection Path

`open_shape_pie` 对 `selection_path` 调用一次 `to_json()`，把同一个字符串写入各 Shape Operator 的 `selection_path_json`。`CutoutSelectionToShape` 通过 `SelectionPath.from_json()` 恢复 Points 与 Invert 后交给栅格器。JSON 保留 `points` 和 `invert`，只删除 `fill_rule`。

相比拆分 Points JSON 与 Bool Property，此方案不会产生两个必须同步的传输值；相比 RNA Collection，它不增加 PropertyGroup、注册顺序和每按钮逐点复制；相比令牌或全局表，它没有生命周期与菜单取消清理问题。

### 3. 使用 non-zero scanline 端点累计

栅格器先裁切路径的几何 bounds，并以像素中心 `x + 0.5`、`y + 0.5` 判断边界。每条非水平边只处理其实际跨越的扫描行，计算交点对应的水平区间终点；按边方向在该行的起点和终点写入正负 winding 变化。全部边处理完成后，每行只执行一次水平累计，累计值非零的像素即为 Selection。

这与当前 `NONZERO` 的射线 crossing 定义相同，但不再为每条边生成二维 `selected` 数组。相比 Pillow，此实现可以明确固定 winding、严格不等号与像素中心语义，并且无需为自交行为依赖第三方未公开约定。

### 4. 非 Invert 使用局部画布

普通 Selection 只创建裁切到图片范围的 Path bounds；启用抗锯齿时在四周增加核半径 2 px，使局部卷积与整图卷积等价。源 Alpha 只切片到同一局部范围。由于 Invert 的有效区域可能覆盖路径外的整图，Invert 继续使用完整图片范围，但仍采用单次 scanline 累计。

最终可见 bounds 使用按行和按列的 `any()` 后查找首尾非空索引，不再通过 `np.nonzero()` 为每个命中像素创建两组坐标。返回值继续是局部 `SelectionMask(values, bounds)`。

### 5. 用结果等价和工作边界验证性能

小尺寸参考实现覆盖普通、凹、自交、重复绕行、越界、水平边、Invert、抗锯齿、Alpha 阈值和空 Selection，并逐值比较 Mask 与 bounds。高分辨率测试验证中间工作数组只按目标画布建立、每条边只产生其跨行事件，不设置依赖 CPU 的秒数断言。

开发验证继续记录代表性 5K/1000 点 Lasso 的基准，用于确认实际数量级改善，但不把机器耗时写成测试契约。

## Risks / Trade-offs

- [Image Tool 自交路径结果改变] → 这是明确的产品决策；更新预览和最终 Mask 测试，使重叠区始终保留。
- [局部抗锯齿在边缘与旧结果不同] → 按固定核半径扩展局部画布，并用逐值测试覆盖图片边缘和越界路径。
- [Invert 无法取得同等局部内存收益] → 保留整图画布以维持语义，但仍消除逐边二维广播和巨大 `nonzero` 坐标数组。
- [扫描线交点在整数顶点重复计数] → 沿用半开 crossing 条件和像素中心判定，以参考实现测试水平边、共顶点与自交路径。
- [Path JSON 仍包含已删除的填充规则] → 更新序列化测试，验证载荷只包含 Points 与 Invert，且不保留旧填充分支。

## Migration Plan

1. 将预览与 Mask 参考语义统一为 non-zero，调整差异测试为重叠区保留测试。
2. 将 `SelectionPath` 精简为 Points 与 Invert，删除 `fill_rule` 并更新 JSON 载荷，迁移共享手势、Image Tool 与 Cutout 的参数边界。
3. 保持 Cutout 的单一 Path JSON Property，由其恢复精简 Path，删除旧填充字段解析。
4. 实现局部 scanline、局部抗锯齿/Alpha 和低内存 bounds，迁移所有调用方。
5. 更新测试和内部文档，运行相关测试、完整测试及代表性 5K 基准。

回退时整体恢复旧 Selection Path 字段和栅格器，不保留两套入口或兼容层。

## Open Questions

无。
