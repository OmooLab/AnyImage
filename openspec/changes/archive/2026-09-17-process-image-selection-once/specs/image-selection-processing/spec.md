## Purpose

规定 Image Tool 与 Cutout 先共享构建轻量 Selection Path，并只在图片编辑或 Shape 生成的执行阶段将其转换为一次 Selection Mask，使高分辨率源图避免重复处理。

## ADDED Requirements

### Requirement: Image editing prepares one Selection
系统 SHALL 在一次 Image Tool 编辑中只读取一次源图 RGBA 并只将 Selection Path 栅格化为一次 Selection Mask，后续本地编辑或 AI 输入准备 MUST 复用该次处理结果。

#### Scenario: User commits a local image edit
- **WHEN** 用户完成 Image Tool 手势且未启用 Refine Selection
- **THEN** 系统使用同一次源图读取和同一个 Selection Mask 完成 Alpha 编辑、裁剪与结果创建

#### Scenario: User commits a refined image edit
- **WHEN** 用户完成 Image Tool 手势且启用 Refine Selection
- **THEN** 系统使用同一次源图读取和同一个 Selection Mask 准备 AI 输入，不为输入导出重复读取或栅格化

### Requirement: Tools share Selection Path construction
系统 SHALL 让 Image Tool 与 Cutout Tool 复用同一条手势主链构建一次内存中的 Selection Path，用户圈选阶段不得为了工具执行而构建 Selection Mask。

#### Scenario: Image Tool gesture completes
- **WHEN** 用户完成任一 Image Tool 手势
- **THEN** 同一个 Operator 将内存中的 Selection Path 直接交给图片编辑执行阶段，不执行 JSON 编解码

#### Scenario: Cutout gesture completes
- **WHEN** 用户完成 Cutout Lasso 或双击全选
- **THEN** 手势主链将内存中的 Selection Path 交给 Shape Pie Menu，且尚未构建 Selection Mask

### Requirement: Selection Path serialization is limited to the Cutout operator boundary
系统 SHALL 仅在 Shape Pie Menu 向 `CutoutSelectionToShape` 传递任意长度 Selection Path 时，将路径编码为一次可由 Blender Operator Property 保存的 JSON 值。

#### Scenario: Cutout Shape buttons are built
- **WHEN** Shape Pie Menu 为当前 Selection Path 创建 Shape 按钮
- **THEN** 菜单将该 Path 编码一次，并把同一个值直接设置给各 `CutoutSelectionToShape` 按钮

#### Scenario: Cutout Shape operation starts
- **WHEN** 用户点击 Shape 按钮
- **THEN** `CutoutSelectionToShape` 从自身 Property 取得并解析 Selection Path，且不依赖令牌、全局状态或 Selection 缓存

### Requirement: Cutout defers Selection Mask construction until Shape selection
系统 SHALL 在 Cutout Shape Pie Menu 打开前只构建并传递轻量的 Selection Path，不得读取源图像素、栅格化 Selection Mask 或扫描可见 Alpha。

#### Scenario: User finishes a Cutout lasso
- **WHEN** 用户松开 Cutout Lasso 并形成有效路径
- **THEN** 系统立即打开 Shape Pie Menu，且尚未执行全分辨率 Selection 像素处理

#### Scenario: User double-clicks a Cutout image
- **WHEN** 用户双击 Image Empty 以选择完整图片
- **THEN** 系统以完整图片的 Selection Path 打开 Shape Pie Menu，且尚未读取或扫描完整图片像素

#### Scenario: User abandons the Shape menu
- **WHEN** 用户关闭 Shape Pie Menu 而未选择 Shape
- **THEN** 系统不读取源图像素、不构建 Selection Mask，也不执行可见 Alpha 扫描

### Requirement: Selected Cutout Shape consumes one Selection
系统 SHALL 让 `CutoutSelectionToShape` 直接接收 Selection Path 的序列化值，并在用户选定 Cutout Shape 后只将其转换为一次可供本地或 AI 主链复用的 Selection Mask。

#### Scenario: User chooses a local Cutout Shape
- **WHEN** 用户选择不需要 AI 的 Surface 或 Balloon
- **THEN** 系统只读取一次源图 RGBA、栅格化一次 Selection Mask，并复用结果完成验证、颜色图和几何创建

#### Scenario: User chooses an AI Cutout Shape
- **WHEN** 用户选择需要 Refine Selection、Depth 或 Normal Map 的 Shape
- **THEN** 系统只读取一次源图 RGBA、栅格化一次 Selection Mask，并复用结果准备持久化的选区输入供后续 Job 阶段消费

#### Scenario: Selected Cutout contains no visible pixels
- **WHEN** 用户选定 Shape 后，Selection 与源图可见 Alpha 没有交集
- **THEN** 系统在该 Shape 操作中报告空 Selection，且不启动 AI Job 或创建 Cutout 对象

### Requirement: Selection optimization preserves results
系统 MUST 保持现有 Image Tool 输出边界、Cutout Shape 候选项、AI 参数和最终图像及几何语义不变。

#### Scenario: Same Selection is processed after optimization
- **WHEN** 相同源图、Selection Path 和工具设置在优化前后提交
- **THEN** 系统产生等价的 Selection 边界、Alpha 结果、AI 输入与 Cutout 几何
