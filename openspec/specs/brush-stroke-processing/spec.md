# brush-stroke-processing Specification

## Purpose
TBD - created by archiving change repair-image-edit-pipelines. Update Purpose after archive.
## Requirements
### Requirement: Stroke simplification bounds the whole segment error
Brush 与共享自由手绘手势 SHALL 将每个保留原始采样点到简化线段的偏差限制在 0.75 个 Viewport 像素以内。Polyline 的已提交顶点 SHALL 按用户输入保留。

#### Scenario: Dense curved stroke is simplified
- **WHEN** 用户以高密度采样绘制弯曲轨迹
- **THEN** 整段简化误差不超过 0.75 px，连续尾点替换不会累计放大偏差
- **AND** 预览与提交使用同一有效路径

### Requirement: Brush antialiases the complete geometric union
Brush SHALL 对全部圆形印记和连接条的完整几何并集应用一次抗锯齿。几何并集相同的图元分段方式 SHALL 产生相同覆盖值。

#### Scenario: Stroke turns through a right angle
- **WHEN** 半径为 2、5 或 25 px 的 Brush 形成直角连接或自交
- **THEN** 内部连接处不会因图元各自的抗锯齿边界减少覆盖
- **AND** 提交覆盖符合完整并集的抗锯齿参考结果

#### Scenario: Equivalent geometry has different segmentation
- **WHEN** 同一个直线 footprint 由不同数量的共线连接条描述
- **THEN** 输出 Alpha 覆盖在浮点误差内一致

### Requirement: Long stroke preview remains responsive
Brush SHALL 在每次有效路径变化后显示整条待提交笔画的合并填充和外轮廓。局部新增笔画的预览计算 SHALL 限定于变化范围，静止重绘 SHALL 复用已有预览结果。

#### Scenario: A short segment is appended to a long stroke
- **WHEN** 已有 800、1600 或 3200 个屏幕点，用户追加只影响局部范围的短线段
- **THEN** 预览更新覆盖新范围并保留其他区域，计算范围不扩展为完整历史笔画
- **AND** 预览与相同路径的完整几何参考一致

#### Scenario: Tail changes or crosses previous geometry
- **WHEN** 活动尾段变化或与已有笔画相交
- **THEN** 预览清除失效尾段的覆盖及内部轮廓，呈现当前完整 footprint

### Requirement: Mask provides one transactional gesture edit
Mask SHALL 在启动时冻结 Scene 的 Gesture、Mode 和 Radius；完成时一次提交 Packed Image 并支持单步 Undo。Mask SHALL NOT 暴露无法执行的操作后参数重做面板。

#### Scenario: Stroke is completed and undone
- **WHEN** 用户完成一个 Brush、Lasso 或 Polyline Mask 后执行 Undo
- **THEN** 源图片与对象状态恢复，整次手势只产生一个编辑步骤

#### Scenario: Stroke is cancelled or tool changes
- **WHEN** 用户按 Esc、RMB，或切换工具取消未提交手势
- **THEN** 原 Image 不变，所有操作内路径与预览资源释放

#### Scenario: User edits tool settings
- **WHEN** 用户修改 Scene 中的 Mask 工具设置
- **THEN** 新手势采用新设置，进行中的手势保持启动时设置

