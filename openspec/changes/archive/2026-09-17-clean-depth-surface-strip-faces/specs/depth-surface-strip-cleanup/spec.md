## ADDED Requirements

### Requirement: 拆边后默认执行单次条带清理

`O Image Depth Plane` 与 `O Image Depth Cutout` SHALL 在 Split 正值分支内、Split Edges 之后且投影和厚度生成之前，通过几何节点执行一次 Face / All 删除。两个节点组 SHALL 共用该逻辑，正式接口 SHALL NOT 暴露 `Remove Strip Faces` 开关。

#### Scenario: 开启 Split
- **WHEN** Split Threshold 大于 0
- **THEN** 系统先按当前规则拆边，再根据拆后拓扑执行一次条带删面

#### Scenario: 关闭 Split
- **WHEN** Split Threshold 为 0
- **THEN** 系统旁路拆边及新增条带删面，保持当前零值分支的几何与投影行为

#### Scenario: 单次删除
- **WHEN** 首次删除使另一张面新出现一组边界对边
- **THEN** 该面不会因新边界在本次求值中被继续删除

### Requirement: 四边面边界对边判定

系统 SHALL 仅选择四边面，并按面角顺序取得四条边。若至少一组对边的 Face Count 均等于 1，该面 SHALL 被选中；其余面 SHALL 被保留。

#### Scenario: 条带及孤立四边面
- **WHEN** 四边面具有两条相对的边界边，或具有三条、四条边界边
- **THEN** 该面被删除

#### Scenario: 普通边缘及角落
- **WHEN** 四边面没有边界边、只有一条边界边，或仅有两条相邻边界边
- **THEN** 该面保留

#### Scenario: 面角起点与绕序
- **WHEN** 同一四边面的面角起点改变或绕序反转
- **THEN** 选择结果不变

#### Scenario: 非四边面
- **WHEN** 输入面为三角面或其他非四边面
- **THEN** 新增清理规则不删除该面

#### Scenario: 非流形边
- **WHEN** 一条边的 Face Count 不等于 1
- **THEN** 该边不能作为匹配条件中的边界边

### Requirement: 清理结果接入原投影和厚度流程

系统 SHALL 在剩余几何上固定相机坐标并执行现有投影及加厚，保留 UV 和用户属性，保持切口区域独立。清理选择 SHALL 只依据拆后拓扑，不依赖 Thickness 或后续 Smooth。

#### Scenario: 剩余区域加厚
- **WHEN** 清理后的定向正确的流形片状区域设置正厚度
- **THEN** 每个保留区域的正背面与侧壁保持完整连接，区域之间保持独立

#### Scenario: 改变显示形状参数
- **WHEN** 基础几何、深度输入与 Split Threshold 不变，仅修改 Thickness 或 Smooth
- **THEN** 被条带清理选中的基础面集合不变

#### Scenario: 属性与空结果
- **WHEN** 清理保留部分面或删除全部面
- **THEN** 求值正常完成且坐标有限；有剩余几何时 UV 与用户属性可用，临时属性依当前流程清理

### Requirement: Split Threshold 位于 Smooth 前

两个节点组 SHALL 将唯一的 `Split Threshold` 输入放在主输入区，紧邻并位于 `Smooth` 之前。该输入 SHALL 保持原名称、FACTOR 类型、0–1 范围、默认 0 和当前阈值映射。

#### Scenario: 检查接口
- **WHEN** 检查任一节点组或其修改器输入
- **THEN** Split Threshold 位于 Smooth 前且不属于 Options，Options 内没有重复输入，接口没有 Remove Strip Faces

#### Scenario: 参数读取
- **WHEN** Operator 为修改器赋值或用户调整 Split Threshold
- **THEN** 新位置的输入正常控制原拆边强度及默认条带清理
