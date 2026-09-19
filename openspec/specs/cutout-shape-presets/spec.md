# cutout-shape-presets Specification

## Purpose
TBD - created by archiving change reorganize-cutout-shapes. Update Purpose after archive.
## Requirements
### Requirement: 四个创建入口映射三个节点组
系统 SHALL 提供 Flat、Solid、Depth Solid、Depth Balloon 四个入口，并默认使用 Solid。Flat 与 Solid SHALL 共用 O Image Cutout；Depth Solid SHALL 使用 O Image Depth Cutout；Depth Balloon SHALL 使用 O Image Depth Balloon。

#### Scenario: 普通默认创建
- **WHEN** 用户以默认形态创建 Cutout
- **THEN** 对象使用 O Image Cutout，Thickness Mode 为 Balloon，Thickness 为 1

#### Scenario: 显式选择入口
- **WHEN** 用户分别选择四个入口
- **THEN** 系统按上述映射加载三个资产，Flat 的 Thickness 为 0，另外三个入口的 Thickness 为 1

### Requirement: 三个节点组直接输出最终几何
三个 Cutout 节点组 SHALL 可直接作为 Geometry Nodes 修改器使用，并承担各自的清理、塑形、平滑与轴向输出。发布资产 MUST 移除旧 Shape 总切换器及旧 Surface、Balloon、Depth Surface 子组。

#### Scenario: 检查新建修改器与发布资产
- **WHEN** 新建任一 Cutout 并检查其修改器与资产
- **THEN** 修改器直接引用对应节点组，不存在跨四种形态的 Shape 输入；Cutout 资产集合恰为三个指定节点组

#### Scenario: 输出轴向
- **WHEN** 对同一输入分别使用 -Z 与 +X 的 Inward Axis
- **THEN** 几何与对象矩阵配对转换，保持相同世界空间位置及正确朝向

### Requirement: 普通与深度 Cutout 具有双厚度方式
O Image Cutout 与 O Image Depth Cutout SHALL 提供 Balloon、Uniform 两种 Thickness Mode，默认 Balloon。Balloon 厚度 SHALL 表示倍率，Uniform 厚度 SHALL 表示距离，输入语义与单位必须明确区分。

#### Scenario: 普通平面与体积转换
- **WHEN** O Image Cutout 的 Balloon Thickness 从 0 调整到 1
- **THEN** 相同基础网格由单层平面变为当前 Balloon 的正背面体积，无需重算 AI 或重建对象

#### Scenario: 等厚板片
- **WHEN** O Image Cutout 选择 Uniform 并设置非零厚度
- **THEN** 输出当前 Surface 的等厚板片形态；厚度为零时输出单层平面

#### Scenario: 厚度单位
- **WHEN** 用户检查或切换两种 Thickness Mode
- **THEN** Balloon 的输入明确为倍率，Uniform 的输入明确为距离，不将一种单位的值隐式解释为另一种单位

### Requirement: Depth Balloon 默认双面
O Image Depth Balloon SHALL 保留原 Depth Balloon 的参考平面塑形行为，并默认开启 Double Sided。

#### Scenario: 默认与单面输出
- **WHEN** 用户创建 Depth Balloon，再关闭 Double Sided
- **THEN** 初始输出采用原算法的双面塑形，关闭后采用原算法的单面塑形，其余参数语义保持一致

### Requirement: 公共网格属性与前置清理
所有入口 SHALL 准备 o_balloon；三个节点组 SHALL 在塑形前复用按原平面岛总面积清理小区域的 Cleanup 规则，并在输出保留 UVMap、o_balloon 与用户属性。

#### Scenario: Flat 后续增厚
- **WHEN** 用户将 Flat 的 Thickness 调为正值
- **THEN** 已有 o_balloon 可直接参与塑形，UV 与材质映射保持有效

#### Scenario: 小岛清理
- **WHEN** 输入包含总面积低于 Cleanup 阈值的独立平面岛
- **THEN** 三个节点组均在塑形前删除该岛，保留大于阈值的岛

