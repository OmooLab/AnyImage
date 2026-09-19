## ADDED Requirements

### Requirement: Selection Mask is independent of image content
系统 SHALL 仅根据 Selection Path、Invert、图片尺寸与抗锯齿设置栅格化 Selection Mask，并且 Selection 栅格化不得读取、接收或合并源图片 Alpha、颜色或 Alpha threshold。

#### Scenario: Images have different Alpha
- **WHEN** 相同 Selection Path、图片尺寸与抗锯齿设置用于透明度内容不同的图片
- **THEN** 系统产生逐值相同且 bounds 相同的 Selection Mask

#### Scenario: Selection is inverted
- **WHEN** Selection Path 启用 Invert
- **THEN** 系统在完整图片画布上产生路径外的纯几何 Selection Mask，而不检查源图片可见内容

### Requirement: Image businesses combine source Alpha explicitly
系统 SHALL 由 Image Tool 与本地 Cutout 在实际业务阶段显式组合 Selection Mask 值和对应 Bounds 内的源 Alpha；Selection Mask MUST 在组合前后保持纯几何值不变。

#### Scenario: Image Tool edits a Selection
- **WHEN** 用户提交未启用 Refine 的 Image Tool Selection
- **THEN** Image Tool 在几何 bounds 内把 Selection 值乘入源 Alpha，并由编辑业务计算内容 bounds、空结果和最终图片

#### Scenario: Local Cutout builds a Shape
- **WHEN** 用户选择不需要 AI 的 Cutout Shape
- **THEN** Cutout 在构建 Shape 时组合局部源 Alpha 与 Selection 值，并使用业务结果约束几何和判断空内容

#### Scenario: Source content is transparent
- **WHEN** 几何 Selection 有效但对应源 Alpha 没有可见内容
- **THEN** 消费该内容的 Image 或 Cutout 业务报告空内容，Selection 栅格化本身仍成功

### Requirement: AI receives one rectangular Bounds image
系统 SHALL 为需要 AI 的 Image Tool 或 Cutout 按 Selection 几何 bounds 写出一份矩形局部 RGBA 文件，并且该文件 MUST 保留 bounds 内的源 Alpha，不得预先乘入 Lasso Selection 值。

#### Scenario: Refine receives Lasso context
- **WHEN** 用户对 Lasso Selection 启用 Refine
- **THEN** BEN2 接收 Lasso 几何 bounds 对应的完整矩形 RGBA，矩形内、Lasso 外的源像素保持原样

#### Scenario: Normal or Depth requires AI
- **WHEN** Cutout 仅因 Normal 或 Depth 进入 AI 流程
- **THEN** Job 使用与 Refine 相同的 Bounds 矩形输入协议，不建立另一套 Masked Selection 输入

#### Scenario: Blender Image source varies
- **WHEN** 源 Image 来自文件、Packed 数据或 Blender 内存
- **THEN** Operator 通过同一个 Bounds 图片序列化入口产生 AI 输入，不按来源建立不同业务主链

### Requirement: Refine may expand within Selection Bounds
系统 SHALL 将 Refine 的 Lasso 解释为矩形上下文范围，而不是 BEN2 输出的硬 Mask；最终 Refine Alpha SHALL 由 BEN2 在该矩形内的结果决定。

#### Scenario: BEN2 preserves content outside Lasso
- **WHEN** BEN2 在 Selection bounds 内保留了 Lasso 路径外的像素
- **THEN** 系统保留这些像素，不再与原始 Lasso Selection Mask 相交

#### Scenario: BEN2 returns no visible content
- **WHEN** Refine 输出在矩形 bounds 内没有可见 Alpha
- **THEN** Refine 业务报告空内容且不创建 Image 或 Cutout 结果

### Requirement: AI operations reuse encoded local images
系统 SHALL 复用 AI 流程中已经编码的局部 RGBA 文件作为最终颜色 Image，不得重新读取完整源图并创建包含相同颜色内容的新内存 Image 后再次编码。

#### Scenario: Image Tool Refine completes
- **WHEN** BEN2 返回已收紧 bounds 的 Refine RGBA 文件
- **THEN** Image Tool 直接加载、配置并 Pack 该文件，然后按响应 bounds 替换源 Image Empty

#### Scenario: Cutout Refine completes
- **WHEN** Cutout 的 BEN2 Refine 返回局部 RGBA 文件
- **THEN** Cutout 使用该文件的 Alpha 构建结果几何，并使用同一个已加载 Image 作为颜色纹理

#### Scenario: Cutout generates only Normal or Depth
- **WHEN** Cutout AI 流程没有 Refine 输出
- **THEN** Cutout 直接加载并 Pack 提交前的 Bounds 输入作为颜色纹理

#### Scenario: AI operation cleans up
- **WHEN** 已有输入或 Refine 输出成功加载并 Pack，或者操作取消
- **THEN** 系统按 Job 生命周期清理临时文件，且 Blender 结果不再依赖临时路径
