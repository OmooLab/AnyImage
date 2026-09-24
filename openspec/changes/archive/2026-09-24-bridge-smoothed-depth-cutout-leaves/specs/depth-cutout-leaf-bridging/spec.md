## ADDED Requirements

### Requirement: Front 与 Rear 使用同源叶片拓扑
`O Image Depth Cutout` SHALL 从投影后的同一最终拓扑构造 Front leaf 与 Rear leaf，只允许改变点位置、属性和面朝向。Rear 位移 SHALL 在 Face domain 求值后应用，并 SHALL 在共同 Boundary Smooth 之前完成 Rear Smooth 与 Flip Faces。Rear Smooth 的 profile strength SHALL 使用 `pow(o_balloon, 0.5)`。

#### Scenario: Face-domain Rear 位移
- **WHEN** 输入面内各点的厚度方向不同且 Thickness 为正
- **THEN** Rear 点位置 SHALL 等于 Face-domain 位移适配到点后的结果
- **AND** 不得以 Point-domain 直接位移替代该结果

#### Scenario: Front 与 Rear 面朝向相反
- **WHEN** 仅输出组合前的 Front 与 Rear
- **THEN** 两张 leaf 的对应面 SHALL 具有相反绕向
- **AND** Rear 不得依赖最终材质双面显示掩盖错误方向

### Requirement: Source index 稳定标识对应点
系统 SHALL 在 Front / Rear 分支之前为最终投影拓扑的每个点保存唯一 source index。Join、Flip Faces、Set Position、Boundary Smooth 与 Separate Geometry SHALL 保留该标识；桥接目标 MUST 按保存的标识查找，不能直接假设当前动态 `Index` 相等。

#### Scenario: Join 与 Separate 后仍能对应
- **WHEN** Front 与 Rear 经 Join、共同平滑并再次拆开
- **THEN** 每个 Front boundary point SHALL 找到 source index 相同的唯一 Rear point
- **AND** 对应线段不得连接到其他 source index

#### Scenario: 对应关系独立于元素排序
- **WHEN** Join 或 Separate Geometry 改变任一 leaf 的当前点序
- **THEN** bridge lookup SHALL 仍返回 source index 相同的 Rear Position
- **AND** Sort Elements 不得用于掩盖缺失、重复或越界的 source index

### Requirement: Wall 仅由对应边界边生成
系统 SHALL 从最终 Front leaf 提取全部 Mesh Boundary Edges，并将每个边界点连接到同源 Rear point 以生成 Wall。实现 MUST 保持逐点 Offset 语义，MUST NOT 使用 Faces Extrude 的 Face-domain Offset 连接任意变形后的两张 leaf。

#### Scenario: 不对称叶片逐点桥接
- **WHEN** Front 与 Rear 是拓扑相同但各点位移不同的不对称非共面网格
- **THEN** 每个 Wall 顶点 SHALL 精确落在对应 Front 或 Rear boundary point
- **AND** Wall 边不得跨越到其他 source index

#### Scenario: 所有开放边界独立闭合
- **WHEN** 网格同时含原始 Outline、洞、Depth Split 与 Depth Limit 形成的开放边界
- **THEN** 每条边界边 SHALL 恰好生成一个 Wall face
- **AND** 不同边界环之间不得产生连接

### Requirement: 最终 Depth Cutout 保持有效闭合
正厚度输出 SHALL 由 Front、反向 Rear 与定向 Wall 组成，并只焊接已经重合的对应端点。零厚度输出 SHALL 只保留 Front，不生成重叠 Rear 或零面积 Wall。

#### Scenario: 正厚度闭合
- **WHEN** Balloon 或 Shell 使用正厚度
- **THEN** 输出 SHALL 坐标有限、无开放边、无零面积面且无跨主体侧壁
- **AND** UVMap、`o_balloon` 与 `o_normal_reduction` SHALL 保持有效

#### Scenario: 零厚度旁路
- **WHEN** 当前模式的厚度为零
- **THEN** 输出 SHALL 是 Boundary Smooth 后的单层 Front
- **AND** 不得求值或输出 Rear 与 Wall
