## ADDED Requirements

### Requirement: Leaf smoothing uses one shared Repeat Zone

Depth Cutout 正厚度路径 SHALL 把同源 Front 与 pre-flipped Rear 作为断开的 mesh islands 输入一个共同 Boundary Smooth Repeat Zone。零厚度路径 SHALL 经同一平滑入口只输入 Front。最终节点组不得保留第二条 leaf smoothing Repeat Zone。

#### Scenario: 正厚度共同平滑
- **WHEN** Thickness 为正
- **THEN** Front 与 Rear SHALL 共同执行一个 Boundary Smooth Repeat Zone
- **AND** Rear SHALL 在该 Repeat Zone 之前完成 Face-domain 位移、Rear Smooth 和 Flip Faces

#### Scenario: 零厚度复用平滑入口
- **WHEN** Thickness 为零
- **THEN** 共同平滑入口 SHALL 只接收 Front
- **AND** Rear、lookup 与 Wall 不得出现在输出中

### Requirement: Bridge mapping uses linear auxiliary work

Source-index lookup、边界提取与 Wall 生成 SHALL 随点数和边界边数线性增长，不得为每个点或每条边复制节点链、执行全网格 nearest 查询或增加嵌套 Repeat Zone。

#### Scenario: 高密度边界桥接
- **WHEN** Depth Cutout 使用超过 4096 个 source points 的正厚度网格
- **THEN** bridge mapping SHALL 只使用固定数量的字段、排序或采样节点
- **AND** Wall face 数 SHALL 等于 Front boundary edge 数
