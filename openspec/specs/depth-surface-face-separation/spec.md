# depth-surface-face-separation Specification

## Purpose
TBD - created by archiving change replace-depth-surface-stretch-with-split. Update Purpose after archive.
## Requirements
### Requirement: 分离控制替换拉伸剔除

系统 SHALL 在 Depth Surface 及外层 Cutout 的 Options 中以 `Split` 替代 `Stretch Limit`。Split SHALL 为范围 `0–1` 的比例输入，默认 `0`，增大时不得降低同一输入几何的切边选择强度。

#### Scenario: 默认关闭
- **WHEN** 用户使用默认 Split `0`
- **THEN** 系统不增加切边，并在 Cleanup 保留的区域上使用原 Depth Surface 采样与投影行为

#### Scenario: 中点与最大强度
- **WHEN** Split 分别设为 `0.5` 和 `1`
- **THEN** 内部深度坡度阈值分别为 `5` 和 `2.5`，且控制值不能超过 `1`；正值对应阈值为 `2.5 / Split`

#### Scenario: 接口替换
- **WHEN** 用户检查新 Cutout 的 Options
- **THEN** 可见 Split，且不存在 Stretch Limit 控制及其拉伸删几何行为

### Requirement: 使用相邻面深度与实际跨度选择共享边

系统 SHALL 以场景尺度的相邻面中心 Z 差除以变形前两面中心的实际距离作为坡度得分；场景深度 SHALL 包含图片标定的 Uniform Scale 和当前 Depth Scale 的幅度。系统 SHALL 只对恰有两个邻面的共享边执行此判断，并安全处理零跨度输入。

#### Scenario: 同一阈值两侧
- **WHEN** Split 为 `0.5`，两个有效邻接的坡度得分分别为 `4` 和 `6`
- **THEN** 得分 `4` 的边不被选中，得分 `6` 的边被选中进行分离

#### Scenario: 等比尺度变化
- **WHEN** 图片几何和经标定的深度同时等比缩放且 Split 不变
- **THEN** 相应共享边的坡度得分和选择结果保持一致

#### Scenario: 深度归零与退化邻接
- **WHEN** Depth Scale 为 `0` 或邻面中心距离为零
- **THEN** 该条件不产生新增切边，且求值不产生非有限坐标

### Requirement: 分离保留表面及两侧独立位置

系统 SHALL 通过拓扑分离保留原始表面的覆盖，使用各自所属侧的数据确定拆后位置。仅设置选边而继续使用共享 UV 的同一个深度值 SHALL NOT 被视为实现两侧分离。

#### Scenario: 零厚度深度阶跃
- **WHEN** Cleanup 为零，规则网格跨越深度阶跃且 Split 选中贯通边界
- **THEN** 原始面全部保留，两侧具有独立顶点与不同场景深度，且没有拉伸剔除造成的缺面

#### Scenario: 开启控制但没有切边
- **WHEN** Split 大于零且所有共享边均未达到分离阈值
- **THEN** 顶点投影与 Split 为零时完全一致，轮廓不因面中心平均而收缩

#### Scenario: 切口保持原相机射线
- **WHEN** 某些共享边被分离
- **THEN** 仅关联顶点使用所属侧的深度，并保持原 XYZ 的相机射线方向；其他顶点保留原采样位置

### Requirement: Cleanup 在拆边后生成厚度前执行

Depth Surface SHALL 在 Split Edges 后、投影及厚度生成前执行一次 Cleanup，按拆分后平面区域的面积使用既有清理阈值。其他 Shape SHALL 保持原 Cleanup 顺序。

#### Scenario: 清理拆出的碎片
- **WHEN** 拆边生成低于 Cleanup 面积阈值的独立区域
- **THEN** 该区域在生成厚度前被清理，其余区域随后投影并加厚

#### Scenario: 厚度不改变清理结果
- **WHEN** Split、基础网格和 Cleanup 保持不变，仅调整 Thickness
- **THEN** 被 Cleanup 保留的平面区域不变

#### Scenario: 关闭分离仍可清理
- **WHEN** Split 为零且 Cleanup 为正
- **THEN** Cleanup 对原平面区域执行一次，不因分离关闭而失效

### Requirement: 厚度侧壁与正背面完整连接

系统 SHALL 在加厚时使每个分离区域的侧壁与正面、背面及相邻厚度段共享连续边界。对定向正确的流形片状输入，各加厚区域 SHALL 形成闭合表面，不得跨区域重新焊接切口。

#### Scenario: 阶跃区域加厚
- **WHEN** 对已拆开的深度阶跃区域设置正厚度
- **THEN** 每个区域的侧壁准确连接其正背面，边界无开口、重叠但未连接的接缝或错位边界

#### Scenario: 分段厚度
- **WHEN** 厚度足以生成多个侧壁段
- **THEN** 各段相接且总厚度符合输入值，侧壁端点与对应表面边界一致

#### Scenario: 近距离独立区域
- **WHEN** 两个独立分离区域的间隔小于既有几何焊接容差
- **THEN** 厚度连接仍保持区域独立，不因全局合并恢复原连接

### Requirement: 正式 Cutout 流程共享分离能力

系统 SHALL 让多个物体共享同一套节点资产，并通过各自修改器传入数据。Split SHALL 仅影响 Depth Surface 分支；外层 Cleanup、Smooth 及其他三种 Shape SHALL 保持各自职责。

#### Scenario: 六物体共享节点
- **WHEN** 三张图片分别创建 High 和 Low 的 Depth Surface
- **THEN** 六个物体引用共享节点组，同一图片的标定值一致，各物体控制值可以独立调整

#### Scenario: 完整修改器链
- **WHEN** Depth Surface 同时启用分离、正厚度及外层 Smooth
- **THEN** 同一区域的正背面和侧壁保持连接，分离区域之间保持独立

#### Scenario: 切换其他 Shape
- **WHEN** 用户改变 Split 后选择其他三种基础 Shape
- **THEN** Split 不改变这些 Shape 的基础拓扑与形状结果

### Requirement: 节点布局清晰可读

资产中全部七个几何节点组 SHALL 遵循 AGENTS.md 的节点组规范：主链从左到右连续排列、辅助分支就近汇入、节点无重叠、保留默认节点标题并隐藏未使用输出。必要的向左引用 SHALL 直接连接，不使用 Reroute 绕行，允许回接连线交叉。

跨区域暂存值 SHALL 使用 `o_depth_*` 命名属性并就近读取，在输出前通过一个 Wildcard 模式的 Remove Named Attribute 统一清理。大步骤之间 SHALL 留白，不放置 String 注解。同一目的的计算 SHALL 聚在主轴同一侧，支线内部间距 SHALL 明显小于与其他部分的距离。独立用途可在两侧错落展开，长算式可超出所服务主链步骤的范围；必要的几何引用可回接。

#### Scenario: 暂存属性生命周期
- **WHEN** Split 和 Thickness 分别开启或关闭
- **THEN** 面、面角和顶点暂存值在正确域传递，输出不残留暂存属性，UVMap 与用户属性保持可用，关闭分支不出现移除缺失属性的警告

#### Scenario: 查看所有几何资产
- **WHEN** 用户打开任一几何节点组
- **THEN** 计算分支按用途聚拢并利用附近空位，长算式横排，局部输入靠近消费节点，布局调整保持原计算结果

#### Scenario: 查看同级分支汇合
- **WHEN** 多个独立同级分支输入 Join Geometry、Menu Switch 或 Combine XYZ 等汇合节点
- **THEN** 分支末端排成一列并对齐输出端，XYZ 三轴按同级输入组织，菜单分支按输入顺序上下排列，共享上游留在公共位置

#### Scenario: 查看同一用途的计算
- **WHEN** 用户查看 Depth Plane 的置换计算或 Depth Surface 的 Split 选边判别
- **THEN** 同一用途的计算聚在主轴同一侧，内部节点间距紧凑，与其他部分之间保留更大的空白，主轴可适当宽松

#### Scenario: 查看分离与厚度流程
- **WHEN** 用户在节点编辑器查看新 Depth Surface
- **THEN** 能沿主链依次辨认采样判别、拆边、投影、厚度和输出，辅助连线不横跨无关区域，节点文字不被遮挡

#### Scenario: 查看成对区域
- **WHEN** 用户检查厚度 Repeat 区域
- **THEN** 成对节点位置正确，循环内部节点清晰排列，区域不遮挡其他节点，Frame 仅用于确有包裹语义的部分

