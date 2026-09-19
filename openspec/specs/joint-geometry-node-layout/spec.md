# joint-geometry-node-layout Specification

## Purpose
TBD - created by archiving change joint-geometry-node-layout. Update Purpose after archive.
## Requirements
### Requirement: 按消费者形成计算块

排列器 SHALL 根据最近的几何消费者集合及字段连通关系划分计算块，并为不同计算块或直接消费节点提供局部接口读取。

#### Scenario: 一组字段服务于相同几何计算
- **WHEN** 相连字段节点具有相同的最近几何消费者集合
- **THEN** 它们作为一个计算块参与排列，复杂计算块用 Frame 表达归属

#### Scenario: 接口值被多个计算区域使用
- **WHEN** 同一接口输出被多个计算区域消费
- **THEN** 各区域通过局部 Group Input 读取相同接口值，接口定义与默认值保持一致

### Requirement: 联合规划计算块与连接通道

排列器 SHALL 在创建最终位置与 Reroute 前，将计算块及共享长连接通道纳入整体空间约束，保留横向计算层次及可区分的块间距。

#### Scenario: 支线之间存在跨列共享连接
- **WHEN** 某个输出跨越多个列连接到其他计算块
- **THEN** 其长连接通道与计算块共同参与空间规划，并根据规划结果创建共享中继

#### Scenario: 几何主线与大型支线共同排列
- **WHEN** 几何处理节点消费大型字段计算块
- **THEN** 两者根据依赖和连接位置共同确定纵向关系，真实节点矩形互不重叠

### Requirement: 布局保持节点行为

排列器 SHALL 保持运算设置、输入默认值、接口、成对区域关系以及去除 Reroute 后的实际连接和多输入顺序；排列前后的代表性几何求值 SHALL 一致。

#### Scenario: 对几何资产执行排列
- **WHEN** 保存排列前后的程序结构及代表性模式的求值结果
- **THEN** 程序结构一致，顶点坐标在测试容差内相等，面连接完全相同

#### Scenario: 再次排列已排列节点组
- **WHEN** 对同一节点组再次执行排列
- **THEN** 实际连接和接口保持一致，局部 Group Input 数量保持稳定

### Requirement: 统一更新全部几何资产

构建工具 SHALL 使用同一排列入口处理资产清单中的全部 GeometryNodeTree，并保存、重新加载及验证更新后的资产。

#### Scenario: 构建节点资产库
- **WHEN** 执行节点资产构建
- **THEN** Image Plane、Image Depth Plane、Image Relief Plane、Image Cutout、Image Depth Cutout、Image Depth Balloon、Image Depth Panorama 共 7 个几何节点组均使用联合规划布局，并通过保存后的资产检查

