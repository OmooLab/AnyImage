## Why

当前颜色匹配主要依赖全局均值和协方差，容易让大面积近似色压过面积较小但视觉关键的颜色；固定五色色板也会重复显示细微差异，不能准确解释迁移关注的颜色。需要让参考签名同时考虑颜色与空间显著性，并让展示复杂度随图片变化。

## What Changes

- 从参考与目标的缩小代理中提取包含面积、颜色独特性、邻域对比和空间连通性的颜色候选。
- 根据加权颜色重建误差动态保留 8–16 个迁移锚点，并使用这些锚点执行色度迁移。
- 从同一迁移签名感知合并出至少 3、最多 7 个展示色块，色块宽度表达合并权重，代表色使用色簇内较高色度的真实像素而非平均色。
- 色块使用正常启用状态呈现真实颜色，不应用 Blender 的禁用灰化外观。
- 保持亮度迁移独立、目标整图 RGB 处理、Alpha 不变、确定性输出和现有 Modal 交互。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `color-reference-matching`: 色度迁移改为使用空间显著、动态数量的颜色签名。
- `color-match-panel`: 固定五色色板改为来自迁移签名的动态加权色板。

## Impact

- `src/anyimage/common/color_match.py` 的参考签名提取、色度迁移与色板输出协议。
- `AnyImageSettings` 的色板派生状态和 `ColorMatchPanel` 的动态绘制。
- 颜色匹配、属性、Panel 与性能相关测试。
- 不增加依赖、用户参数、AI 或 Job Server 路径。
