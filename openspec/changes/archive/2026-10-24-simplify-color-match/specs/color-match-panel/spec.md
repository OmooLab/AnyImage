## MODIFIED Requirements

### Requirement: Color Match Panel explains the reference palette
系统 SHALL 使用 materialyoucolor 的 Celebi 与 Score 从可见参考像素选择最多四种代表色。评分 SHALL 综合色度、颜色占比与色相差异，并关闭排除低占比颜色的硬过滤。色板 SHALL 独立于迁移算法，忽略完全透明像素，按 Alpha 加权。色块 SHALL 正常显示颜色，以候选颜色归并后的近似面积权重确定宽度，不使用禁用灰化状态。少色图 SHALL 仅显示有效代表色，不补造颜色。

#### Scenario: A saturated accent occupies a small area
- **WHEN** 参考包含大面积低色度背景和较小面积鲜艳点缀
- **THEN** 点缀参与候选评分，不因小面积被硬过滤，并可凭色度及色相差异进入色板

#### Scenario: Palette widths are displayed
- **WHEN** 系统显示已选出的代表色
- **THEN** 宽度表示归并后的归一化面积权重，而非评分值

#### Scenario: A neutral reference is selected
- **WHEN** 参考只有灰色或少量有效颜色
- **THEN** 色板显示有效代表色且不生成默认蓝色等额外颜色

#### Scenario: The reference is cleared
- **WHEN** 用户清空参考
- **THEN** 清空色板颜色、数量、权重与参考准备数据

### Requirement: Color reference gallery stays compact
系统 SHALL 以紧凑缩略图显示侧边栏参考图画廊，并同步限制弹出选择窗口的缩略图尺度。尺寸调整 MUST NOT 改变候选、选择或清空语义。

#### Scenario: User opens the reference selector
- **WHEN** 用户在 Color Match Panel 打开参考图选择器
- **THEN** 侧边栏画廊与弹出候选使用紧凑缩略图显示
