## Why

当前 Selection 栅格化按路径的每条边重复扫描二维像素区域，5K 图片上的千点 Lasso 单次处理约需 4 秒并产生大量整图临时数组。`SelectionPath` 需要共同保存路径点与反选状态，但其中的两种填充规则没有继续保留的价值；产品实际期望所有重叠圈选区域都被保留。

## What Changes

- **BREAKING**：所有 Selection 统一使用 non-zero winding 填充，删除 `EVEN_ODD`、`fill_rule` 及其分支；自交或重复绕行的同方向重叠区域始终保留。
- **BREAKING**：将 `SelectionPath` 精简为只包含普通二维点数组和 `invert` 的不可变值，删除 `fill_rule`，保留完整 Path 的 `to_json()` / `from_json()`。
- Cutout Pie Menu 继续把完整 `SelectionPath` 编码一次并交给 Shape Operator，不拆分 Points 与 Invert，也不引入 RNA Collection、令牌或额外状态。
- 使用按扫描行交点累计的局部 scanline 算法替换逐边二维像素广播，并保持现有像素中心判定、Invert、抗锯齿、Alpha 阈值、空 Selection 与最终 bounds 语义。
- 抗锯齿、源 Alpha 合并和可见 bounds 计算只处理必要的局部画布；Invert Selection 仍按完整图片范围处理。
- 增加逐像素等价性、不同路径规模的复杂度边界和高分辨率性能回归测试，不使用机器相关的固定耗时阈值。

## Capabilities

### New Capabilities

- `selection-rasterization`: 规定精简 Selection Path 的统一 non-zero 填充语义、局部 scanline 栅格化结果和高分辨率复杂度边界。

### Modified Capabilities

无。

## Impact

- 影响 `common/selection.py`、`common/viewport.py`、Image Tool、Cutout Tool 及其交互测试和内部文档。
- Cutout Operator 的内部 Selection 参数会改变；它不是公开用户 API，但旧 Operator 参数不再兼容。
- 不新增运行时依赖，不修改 AI Job 协议、Cutout Shape、Mask 抗锯齿核或最终图片与几何处理链。
