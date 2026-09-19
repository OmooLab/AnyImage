# cutout-symmetry-seam Specification

## Purpose
TBD - created by archiving change refine-cutout-symmetry-seam. Update Purpose after archive.
## Requirements
### Requirement: 切口落在对称面上

对称节点 SHALL 让切口边缘落在对称面上，零厚度与非零厚度输入走同一条折叠路径：越过对称面的顶点 SHALL 拉回对称面，只删除因此整体落在对称面上的面，并删除折叠后仍邻接两个面的内部贴平边及其邻接面。保留几何中不得存在越过对称面的顶点，也不得留下整体落在对称面上的面或四面共边。

#### Scenario: 折叠过界部分

- **WHEN** 输入几何的一部分穿过对称面
- **THEN** 跨界面的面保留，越界顶点对称轴坐标归零，界内顶点位置不变
- **AND** 保留几何中不存在越过对称面的顶点

#### Scenario: 清理内部贴平边

- **WHEN** 折叠后出现落在对称面上、且仍邻接两个面的边
- **THEN** 这条边及其邻接面被删除，切口重新成为边界边
- **AND** 输出中不存在四面共边

#### Scenario: 不同厚度得到同一切边位置

- **WHEN** 同一 Cutout 分别以零厚度与非零厚度连接到对称节点
- **THEN** 两种情况都折叠并把切口边缘归零，切边落在对称面上
- **AND** 两侧顶点关于对称面对称，且都不越过对称面的几何尺度派生容差

#### Scenario: 裁切后不留平面面片

- **WHEN** 切口边缘归零使某个面完全落到对称面上，或输入本身存在这类面
- **THEN** 该面不出现在输出中

#### Scenario: 几何全部位于界外

- **WHEN** 输入几何整体越过对称面
- **THEN** 输出为空几何，节点不报错

### Requirement: 接缝由镜像合并自焊

对称节点 SHALL 在镜像之前完成切口归零，使两侧切口顶点重合，并 SHALL 在合并后形成共享边。开启 Fill Sides 时输出网格 SHALL 封闭，且边与顶点流形。

#### Scenario: 开启补面的封闭结果

- **WHEN** Fill Sides 开启且输入包含跨对称面的几何
- **THEN** 输出的每条边恰好邻接两个面，顶点与边满足流形性，面绕序一致
- **AND** 两侧顶点关于对称面对称

#### Scenario: 关闭补面

- **WHEN** Fill Sides 关闭
- **THEN** 切口仍吸附到对称面并完成自焊
- **AND** 开边只出现在没有侧壁的外轮廓处

### Requirement: 补面只覆盖不落在对称面上的边界边

Fill Sides 生成的侧壁 SHALL 只连接不落在对称面上的边界边，落在对称面上的切口环 SHALL 不生成侧壁几何。补面选择 SHALL 按顶点是否越过对称面容差判断。

#### Scenario: 切口处不生成侧壁

- **WHEN** Fill Sides 开启且切口环顶点归零后落在对称面上
- **THEN** 输出中不存在顶点全部落在对称面上的补面面片
- **AND** 切口环在合并后为共享边

#### Scenario: 外轮廓仍生成侧壁

- **WHEN** 输入外轮廓的边界顶点不落在对称面上
- **THEN** 这些边界按现有直壁或平滑侧壁构成连接
- **AND** Fill Sides 关闭时不生成侧壁

### Requirement: 切边平滑独立控制

`Seam Smooth` SHALL 控制切口环的面内平滑次数，`Fill Smooth` SHALL 控制 front 衔接带的面内平滑次数。两者都只移动面内分量并锁定对称轴坐标。侧壁细分 SHALL 始终存在，不以 `Fill Smooth > 0` 为开关。`Seam Smooth` 为 0 SHALL 保持原始切口，`Fill Smooth` 为 0 SHALL 保持原始轮廓；两个参数 SHALL 互不影响，且都与 Fill Sides 独立。

`Seam Smooth` 按切口环的两圈渐变衰减，切口环按 `pinned-geometry-smoothing` 的 `Pin Boundary` 与 `Pin Sharp` 处理。`Fill Smooth` 的锚点 SHALL 是 front 的完整边界带，即界外轮廓与对称面上的切缝，SHALL 按四圈渐变衰减并覆盖对称轴上的点；衔接处不是网格边界，因此 MUST NOT 套用 `Pin Boundary`，只保留 `Pin Sharp`。

#### Scenario: 切边平滑保持切口落在对称面

- **WHEN** Seam Smooth 大于 0
- **THEN** 切口环顶点的对称轴坐标保持在容差内，镜像对称关系成立
- **AND** 平滑位移从切口环起按两圈渐变衰减，两圈之外保留表面顶点位置不变

#### Scenario: 两个平滑参数互不影响

- **WHEN** 只改变 Fill Smooth 或只改变 Seam Smooth
- **THEN** 前者只改变衔接带及其侧壁，后者只改变切口环及其两圈渐变范围
- **AND** Seam Smooth 为 0 时切口保持原始形态，Fill Smooth 为 0 时轮廓保持原始形态且侧壁仍保持细分

#### Scenario: 衔接带覆盖对称轴

- **WHEN** Fill Smooth 大于 0
- **THEN** 界外轮廓与对称轴上的点都产生面内位移
- **AND** 位移从完整边界带向内按四圈渐变衰减

#### Scenario: 关闭补面仍可平滑切边

- **WHEN** Fill Sides 关闭且 Seam Smooth 大于 0
- **THEN** 切口环仍按该参数平滑，侧壁不生成，Fill Smooth 无可作用的轮廓

### Requirement: 节点不引入布尔与裁切

对称节点 SHALL 沿用现有节点集合完成切口，不新增布尔、裁切或细分节点。

#### Scenario: 检查构建结果

- **WHEN** 检查构建出的 `O Image Cutout Symmetry` 节点组
- **THEN** 节点图中不存在布尔类节点
- **AND** 接口在原有输入之外只新增 Seam Smooth

