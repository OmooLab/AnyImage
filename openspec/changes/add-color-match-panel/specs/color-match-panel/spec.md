## ADDED Requirements

### Requirement: Color Match Panel presents the scene reference
系统 SHALL 在 3D View 的 AnyImage 侧边栏第二位提供独立的 `Color Match` Panel，并 SHALL 使用带图片缩略图的 Image 画廊呈现当前 Scene 的 Color Reference。该画廊 SHALL 同时用于选择、替换和清空参考，且新 Scene 的参考 SHALL 默认为空。

#### Scenario: No reference has been selected
- **WHEN** 用户打开尚未选择 Color Reference 的 Scene
- **THEN** `Color Match` Panel 的画廊选择空候选

#### Scenario: A reference is selected
- **WHEN** 用户从画廊选择一个允许的 Image 缩略图
- **THEN** 当前 Scene 的 Color Reference 指向该 Image，画廊显示该 Image 为当前项

#### Scenario: The reference is replaced or cleared
- **WHEN** 用户在画廊中选择另一 Image 或空候选
- **THEN** 当前 Scene 的 Color Reference 对应替换或变为空，且不修改任一 Image 的内容

### Requirement: Color Match Panel explains the reference palette
系统 SHALL 在参考画廊下显示五个代表性色块，并 SHALL 在 Color Reference 改变时根据参考图可见像素更新。色板 MUST 忽略完全透明像素，并 MUST 仅作为连续参考统计的视觉说明，不得将最终匹配限制为五种颜色。

#### Scenario: A reference is selected
- **WHEN** 用户选择具有可见像素的 Color Reference
- **THEN** Panel 显示五个由该参考确定性提取的代表性色块

#### Scenario: The reference is cleared
- **WHEN** 用户清空 Color Reference
- **THEN** Panel 清空色板显示值且不保留上一张参考的颜色

### Requirement: Reference choices exclude generated image categories
系统 SHALL 仅在 Color Reference 画廊中提供尺寸有效的静态 Image，并 MUST NOT 提供逻辑名称以 `_normal`、`_depth` 或 `_color` 结尾的 Image。后缀判断 SHALL 不区分大小写，并 SHALL 忽略 Blender 追加的 `.数字` 重名后缀。

#### Scenario: A regular static image is available
- **WHEN** 一个尺寸有效的静态 Image 名称不属于被排除的后缀类别
- **THEN** 该 Image 以缩略图候选出现在画廊中

#### Scenario: A generated image category is available
- **WHEN** Image 的名称为 `Subject_normal`、`Subject_depth`、`Subject_color` 或这些名称带 Blender 数字重名后缀的形式
- **THEN** 该 Image 不出现在 `Reference` 候选中

#### Scenario: An animated or empty image is available
- **WHEN** Image 为 Movie、Sequence、其他动画来源，或没有有效像素尺寸
- **THEN** 该 Image 不出现在 `Reference` 候选中

### Requirement: Matching reads the panel selection directly
系统 SHALL 继续将 `AnyImageSettings.color_reference` 作为颜色匹配的唯一参考来源。选择框为空、保存的 Image 失效或当前目标就是参考时，`Match Color Reference` SHALL 不可执行，且系统 MUST NOT 自动选择其他 Image。

#### Scenario: A valid panel reference and another target exist
- **WHEN** 用户已在 Panel 选择有效参考，且当前图片目标是另一有效静态 Image
- **THEN** `Match Color Reference` 使用选择框显示的 Image 作为唯一参考

#### Scenario: The panel reference is empty
- **WHEN** `Reference` 选择框为空
- **THEN** `Match Color Reference` 不可执行且不回退到当前选择或其他 Image
