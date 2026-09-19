## ADDED Requirements

### Requirement: Compact repeat execution path

排列器 SHALL 按循环执行的几何步骤安排 Repeat 两端，取值支线独立排列。

#### Scenario: Set Position loop with long value calculations
- **WHEN** 循环只执行 Set Position，输入值来自长计算链
- **THEN** Repeat 两端保持围绕 Set Position 的紧凑排列，预览执行区域按几何主链确定

### Requirement: Geometry processing order

排列器 SHALL 将前置循环安排在后续几何处理之前。

#### Scenario: Depth Cutout boundary smoothing
- **WHEN** 排列 O Image Depth Cutout 的前置边界平滑循环
- **THEN** 循环位于其后续几何消费者左侧，保持原有连接与求值结果

### Requirement: Readable field branches and geometry references

排列器 SHALL 将取值支线紧凑安排在消费者附近，复杂支线使用互不重叠的 Frame，并分离几何引用的水平通道。

#### Scenario: Long calculation chain
- **WHEN** 消费者使用较长的简单计算链
- **THEN** 计算链使用紧凑折叠及分段纵向布局
- **AND** 连续依赖按计算方向展开，独立计算按实际消费输入分组

#### Scenario: Complex depth cutout branches
- **WHEN** 排列 O Image Depth Cutout
- **THEN** 复杂计算支线分别成框，几何引用线保持独立的水平通道，并通过斜向曲线过渡，原有几何求值保持一致

#### Scenario: Geometry trunk alongside its consumer frame
- **WHEN** 几何主干向 Frame 内的计算节点供值
- **THEN** 主干与完整 Frame 边界保持间距，通过斜向分支接入框内消费者

#### Scenario: Long branch near its geometry consumer
- **WHEN** 较大支线需要占用来源和消费者之间的横向空间
- **THEN** 主线在消费者之前预留支线及斜向出口的空间，连续主线保持直接向前连接

#### Scenario: Independent calculation before a geometry consumer
- **WHEN** 支线独立于上游几何结果
- **THEN** 支线可向主线起点之前展开，主线按实际出口位置保持紧凑

#### Scenario: Return connection and neighboring reference tracks
- **WHEN** 几何结果连接左侧消费者
- **THEN** 连线直接向消费者方向过渡，各水平通道按最终范围保留间距

#### Scenario: Geometry fanout without overlapping wires
- **WHEN** 同一几何结果供多个节点消费
- **THEN** 近处消费者直接接入，公共水平通道按从左到右分发，每段公共连线只绘制一次
- **AND** 水平连线保持向前，短 reroute 间距合并，近乎平行的曲线与主线保持间距

#### Scenario: Shared results outside calculation branches
- **WHEN** 几何或其他类型的结果供多个支线消费
- **THEN** 共享结果沿支线外围的公共管道分发，在消费者附近斜向接入
- **AND** 原有主线连接保持执行顺序，公共管道与节点、Frame 及其他管道保留间距

#### Scenario: Geometry transits an unrelated calculation
- **WHEN** 几何连接沿途经过其他支线
- **THEN** 整段曲线绕开不消费该结果的 Frame，仅允许进入自身来源或消费者所属的 Frame

#### Scenario: Peripheral producers feed their shared pipes forward
- **WHEN** 支线计算的结果通过公共管道供多个消费者使用
- **THEN** 共享计算支线与管道一同位于消费者外围，管道入口在结果输出节点右侧
