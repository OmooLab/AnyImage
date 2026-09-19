## ADDED Requirements

### Requirement: Cutout offers persistent gesture selection

Cutout SHALL 提供 Lasso 和 Polyline 手势，默认 Lasso，并保存到 Scene 的独立 Cutout 设置。

#### Scenario: User selects Polyline
- **WHEN** 用户将 Cutout Gesture 切换为 Polyline 并开始剪出
- **THEN** 工具以首次左键按下的位置为起点，随后通过点击添加顶点

#### Scenario: User returns to Cutout
- **WHEN** 用户选择 Polyline 后切换到其他工具再返回
- **THEN** Cutout 继续使用 Polyline，Mask Gesture 保持自己的设置

#### Scenario: Default Lasso interaction
- **WHEN** 新 Scene 中用户拖动 Cutout 并释放左键
- **THEN** 工具以 Lasso 收集轮廓并在有效选区完成后打开 Shape 饼菜单

### Requirement: Cutout reuses shared Polyline interaction

Cutout MUST 复用 Mask 所用的共用 Polyline 手势，提供轮廓预览、起点闭合提示、左键添加顶点、Backspace 删除末点、点击起点或双击或 Enter 完成，以及 RMB、Esc 和切换工具取消。

#### Scenario: User completes a polygon
- **WHEN** 至少三个顶点后，用户点击起点闭合范围内、双击或按 Enter / Numpad Enter
- **THEN** 工具提交已确认的闭合 SelectionPath 并打开 Shape 饼菜单，闭合点击和双击第二击不添加重复顶点

#### Scenario: Too few points
- **WHEN** 少于三个顶点时用户尝试完成
- **THEN** 工具继续收集顶点，不打开 Shape 菜单

#### Scenario: User edits or cancels a polygon
- **WHEN** 用户按 Backspace，或通过 RMB、Esc、切换工具取消
- **THEN** Backspace 删除末点并至少保留起点；取消清理预览且不创建结果对象

#### Scenario: Empty click preserves the source
- **WHEN** 用户在空白处启动 Cutout 手势
- **THEN** 工具保持现有源对象选择规则，不因空白点击清空源对象

### Requirement: Polyline initializes Depth Solid with Uniform mode

通过 Polyline 创建 Depth Solid 时，系统 MUST 将新对象的 `O Image Depth Cutout` 修改器 Mode 初始化为 Uniform。手势 MUST 使用本次提交快照。

#### Scenario: Polyline depth result completes asynchronously
- **WHEN** 用户提交 Polyline 并选择 Depth Solid，在生成结束前将 Cutout Gesture 改为 Lasso
- **THEN** 本次结果的 Mode 仍为 Uniform，用户可在创建后手动调整

#### Scenario: Lasso or another shape is used
- **WHEN** 用户通过 Lasso 创建 Depth Solid，或通过 Polyline 创建 Flat、Solid、Depth Balloon
- **THEN** 对象沿用该 Shape 的现有 Mode 初始化规则

### Requirement: Uniform thickness defaults to half a unit

`O Image Depth Cutout` 的 Uniform Thickness socket MUST 默认 0.5，保存资产中对应显示为 Thickness 的 socket 和新建修改器 MUST 使用该值。

#### Scenario: Node asset is built and loaded
- **WHEN** 完成节点资产构建并从资产加载节点组创建 Polyline Depth Solid
- **THEN** Mode 为 Uniform，Uniform 厚度值为 0.5，通用 Thickness 初始化不会覆盖该值
