## ADDED Requirements

### Requirement: Unified quality meshing
系统 SHALL 在 Fine Outline 两种状态下使用 Tangle Python 版构建最终基础三角网格，采用 10°质量目标及与有效世界边长 h 对应的最大面积 √3/4 × h²。系统 SHALL 保持现有世界 Edge Length、相对下限和非均匀缩放语义，允许细结构产生短于 h 的边。

#### Scenario: Shared density controls
- **WHEN** 相同物理主体更换分辨率、透明画布或对象旋转后创建 Cutout
- **THEN** 同一有效 h 驱动三角化；两种 Fine Outline 模式均使用 Tangle

#### Scenario: Acute constrained feature
- **WHEN** 必须保留的细结构包含尖角或短约束
- **THEN** 系统保留结构，报告实际质量统计，不以删除有效结构强行满足最短边或角度目标

### Requirement: Outline mode defines holes
系统 SHALL 在关闭 Fine Outline 时填充所有封闭内部孔洞并概括外轮廓；开启时仅在孔最长世界跨度 ≤ 0.25h 且面积 ≤ 0.04h² 时填孔，保留其他孔洞。系统 SHALL 从处理后区域重建组件，且不修改原图片和材质 Alpha。

#### Scenario: Fine mode keeps a moderately small hole
- **WHEN** 孔最长跨度为 0.9h，或细长孔的最长跨度大于 0.25h
- **THEN** 开启 Fine Outline 时孔被保留，即使孔面积很小

#### Scenario: Fine mode fills a micro hole
- **WHEN** 封闭孔满足两个微孔条件
- **THEN** 开启 Fine Outline 也填充该孔，后续支撑和三角化使用填孔结果

#### Scenario: Coarse mode fills a nested hole
- **WHEN** 关闭 Fine Outline，内部孔包含独立前景岛
- **THEN** 填孔后区域重新合并，不产生重叠面；与外部背景相通的凹口仍属于外轮廓

### Requirement: Continuous interior support
系统 SHALL 在两种模式下按实际质量网格补足内部支撑。系统 SHALL 拆分两端位于边界的内部弦，为孤立全边界三角形添加内部点，保持细分支经关节到主体的连续内部连接。

#### Scenario: Coarse branch requires support
- **WHEN** 低密度网格的细腿或根部缺少内部顶点
- **THEN** 系统添加局部支撑，Poisson 求解后内部顶点高度为正，不产生全零高度三角形

#### Scenario: Dense region already has support
- **WHEN** 网格区域已经具有连续内部支撑
- **THEN** 系统保持该区域，不生成额外全局中线约束，不重新三角化

### Requirement: Final constraints and topology are validated
系统 SHALL 验证面积、轮廓约束链、孔洞和组件数量、非退化性，且局部支撑拆分 SHALL 保持已验证的轮廓、拓扑与面朝向。像素角自接触 SHALL 做亚像素分离并重新验证。

#### Scenario: Pixel-corner hole contact
- **WHEN** 孔洞轮廓在像素角形成零宽自接触
- **THEN** 系统分离接触点，生成拓扑有效且保留孔洞的网格

#### Scenario: Mesher loses a boundary constraint
- **WHEN** 后端遗漏边界约束或产生错误面积
- **THEN** 系统明确失败，不创建残缺对象

### Requirement: Height support preserves mesh quality
系统 SHALL 在单次局部拆分中补足支撑，并限制累计顶点数。最终角度允许低于基础三角化的 10°目标，验收 SHALL 同时检查角度、连续正高度与压平面积。

#### Scenario: Connected depth samples collapse
- **WHEN** 深度投影将相邻顶点映射到数值上重合的位置
- **THEN** 系统按当前平均边长的百万分之一合并已连接重合点，壳体厚度保持正确方向

### Requirement: Blender distribution and bounded execution
系统 SHALL 分发固定版本的 Tangle Python 源码和 MIT 许可，通过内存数值接口调用，仅使用标准库作为 Tangle 自身依赖。系统 SHALL 隔离调用状态，保持 Blender 数据创建在主线程，并对资源超限明确终止。

#### Scenario: Clean Blender installation
- **WHEN** 在项目支持的 Blender 环境加载插件并创建 Cutout
- **THEN** Tangle 无需用户 pip 安装或外部编译器即可调用，源码和许可被分发规则收录

#### Scenario: Repeated and failed calls
- **WHEN** 连续构建不同输入，包含一次无效输入或资源超限
- **THEN** 后续调用不受先前状态影响，Decimal 上下文保持隔离，失败不创建残缺对象

#### Scenario: Local and AI return paths
- **WHEN** 同步创建或 AI 返回后创建 Cutout
- **THEN** 两者采用捕获的 Fine Outline 设置及同一有效世界边长与网格校验规则
