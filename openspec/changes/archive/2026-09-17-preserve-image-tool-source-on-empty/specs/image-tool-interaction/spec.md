## ADDED Requirements

### Requirement: Image tools preserve Blender object picking
Mask、Rectify 与 Cutout SHALL 使用 Blender 原生 Viewport Picker 决定点击命中的对象和 active object。系统 MUST NOT 按对象类型过滤原生命中结果，也 MUST NOT 在命中非 Image Empty 后恢复先前的图片选择。

#### Scenario: Another Image Empty is clicked
- **WHEN** 一个 Image Empty 为 active，用户使用 Mask、Rectify 或 Cutout 点击另一可拾取的 Image Empty
- **THEN** Blender 原生选择 SHALL 激活被点击的 Image Empty，且本次事件不得启动图片操作

#### Scenario: A non-image object is clicked
- **WHEN** 一个 Image Empty 为 active，用户使用 Mask、Rectify 或 Cutout 点击可拾取的 Mesh、Light 或其他非 Image Empty
- **THEN** 系统 SHALL 保留 Blender 对该对象的原生选择结果，且本次事件不得启动图片操作

### Requirement: Drawing image tools preserve the active source on an empty hit
当已选择的 active object 是 Image Empty 时，Mask、Rectify 与 Cutout MUST 在原生 Picker 没有命中对象时保留该 active source，并 MUST NOT 因 `deselect_all` 清空选择。透明图片像素与 Viewport 空白 SHALL 使用相同的空命中语义。

#### Scenario: Mask starts on a transparent or empty location
- **WHEN** 已选择的 active Image Empty 存在，用户以 Mask 在没有原生对象命中的位置按下鼠标
- **THEN** 系统 SHALL 保持该 Image Empty active 并以该位置开始当前 Mask Gesture

#### Scenario: Rectify starts on a transparent or empty location
- **WHEN** 已选择的 active Image Empty 存在，用户以 Rectify 在没有原生对象命中的位置按下鼠标
- **THEN** 系统 SHALL 保持该 Image Empty active 并把该位置作为第一个 Rectify 点

#### Scenario: Cutout lasso starts outside pickable image content
- **WHEN** 已选择的 active Image Empty 存在，用户以 Cutout 从没有原生对象命中的位置开始拖动
- **THEN** 系统 SHALL 保持该 Image Empty active 并开始 Cutout Lasso

#### Scenario: Cutout full image starts from an empty location
- **WHEN** 已选择的 active Image Empty 存在，用户以 Cutout 在没有原生对象命中的位置双击
- **THEN** 系统 SHALL 保持该 Image Empty active 并打开整图 Cutout Shape 选择

#### Scenario: Cutout empty click keeps the source
- **WHEN** 已选择的 active Image Empty 存在，用户以 Cutout 单击没有原生对象命中的位置且没有形成拖动或双击
- **THEN** 系统 SHALL 保持当前选择且不启动 Cutout Shape 选择

### Requirement: Image operation eligibility uses the active selected Image Empty
Mask、Rectify 与 Cutout SHALL 仅在当前 active object 是已选择的 Image Empty 时开始图片操作。系统 MUST NOT 在工具激活时保存隐藏 source，也 MUST NOT 使用先前 active 的图片绕过当前选择。

#### Scenario: Active object is not an Image Empty
- **WHEN** 当前 active object 是非 Image Empty 或没有已选择的 active object，用户尝试开始 Mask、Rectify 或 Cutout
- **THEN** 系统 SHALL 取消本次图片操作并提示选择 active Image Empty

### Requirement: Gesture validity is decided after collection
Mask、Rectify 与 Cutout MUST NOT 根据起始点是否位于图片画布或是否命中非零 Alpha 决定能否开始手势。系统 SHALL 在手势提交阶段使用各工具现有的图片相交、可见内容和有效几何规则决定是否执行。

#### Scenario: Gesture starts outside and later overlaps the image
- **WHEN** Mask、Rectify 或 Cutout 的起始点位于图片外，但完成的手势与图片有效相交
- **THEN** 系统 SHALL 按完整手势执行对应图片操作

#### Scenario: Completed gesture remains outside the image
- **WHEN** 完成的 Mask、Rectify 或 Cutout 手势与图片没有有效相交
- **THEN** 系统 SHALL 在提交阶段取消操作并报告对应 warning

### Requirement: Frame keeps its existing empty-click selection behavior
Frame SHALL 保持 Blender 风格的空白点击取消选择行为，不得因 Mask、Rectify 与 Cutout 的空命中策略而改变。

#### Scenario: Frame clicks an empty viewport location
- **WHEN** 用户在 Frame 激活时普通点击没有原生对象命中的 Viewport 位置
- **THEN** Frame 的原生选择 keymap SHALL 继续请求 deselect all
