## ADDED Requirements

### Requirement: Fine Outline selects the mesh algorithm
系统 SHALL 提供默认开启的 Fine Outline 设置。开启 SHALL 使用精细轮廓和连续内部支撑算法；关闭 SHALL 使用原始轮廓平滑、概括与均匀布点算法。以下精细网格要求适用于开启状态。

#### Scenario: User chooses abstraction for a fern
- **WHEN** 用户关闭 Fine Outline 并创建任一 Cutout Shape
- **THEN** 系统使用原算法，Mesh Detail 和 Alpha Threshold 继续有效

#### Scenario: New scene uses fine outlines
- **WHEN** Scene 或 Operator 使用默认属性
- **THEN** Fine Outline 为开启状态，界面在 Mesh Detail 旁提供切换

#### Scenario: Settings change during an AI job
- **WHEN** 用户打开 Shape 菜单后修改 Scene 的 Fine Outline
- **THEN** 已发起操作的本地或 AI 返回创建使用菜单捕获的模式


### Requirement: Detail controls actual contour accuracy
系统 SHALL 根据有效 Mesh Detail 同时确定内部目标间距和源轮廓近似精度，保留 Low 的形状概括；High 与 Ultra SHALL 从源轮廓恢复更精细的边缘，而非仅拆分已有直边。系统 SHALL 分别记录相对源轮廓的双向采样误差和网格数量。

#### Scenario: Curved outline is refined at higher detail
- **WHEN** 未触及网格上限的弧线样本分别使用 Low、High、Ultra 构建网格
- **THEN** High 与 Ultra 的实际边界包含恢复曲率的新位置，双向 P95 误差低于 Low，Ultra 在规定数值容差内不劣于 High

#### Scenario: Source-pixel spacing and mesh limit remain effective
- **WHEN** 用户选择四档 Mesh Detail 或输入触及现有网格上限
- **THEN** 内部目标间距沿用 32、16、8、4 源像素及上限调整规则，轮廓精度采用相应有效档位

### Requirement: Cleanup preserves connected thin structures
系统 SHALL 按独立前景区域面积过滤极小碎片，默认阈值为 16 源像素，保留最大区域。系统 SHALL 保留主体连接的细长结构、有效孔洞及原材质 Alpha。

#### Scenario: Tiny islands accompany an insect
- **WHEN** 昆虫主体、与主体相连的单像素细腿和多个小于阈值的独立岛同时存在
- **THEN** 系统移除极小独立岛，保留主体和细腿，原图片像素保持一致

#### Scenario: Entire subject is smaller than the cleanup threshold
- **WHEN** 唯一有效区域小于默认面积阈值
- **THEN** 最大区域被保留并获得有效网格和内部支撑

#### Scenario: Empty selection contains no foreground
- **WHEN** 当前阈值下没有有效前景
- **THEN** 系统返回现有无有效 Selection 的错误结果，不创建空对象

### Requirement: Thin branches retain continuous interior support
系统 SHALL 为过滤后可表示的细长分支提供稀疏连续的内部网格路径，覆盖端部和关节。路径 SHALL 位于有效区域内部，分支连通性 SHALL 在密度变化后维持；已断开的 Alpha 区域独立处理。

#### Scenario: Leg changes width at a joint
- **WHEN** 细腿经较宽关节继续延伸，且内部目标间距大于腿宽
- **THEN** 腿内保持单列内部支撑与连续实际网格边，关节不会因宽度筛选丢失连接

#### Scenario: Density and translation change
- **WHEN** 同一弯腿样本在 Low、Medium、High、Ultra 和平移 1 像素后生成
- **THEN** 各次端部与关节检查位置均由同一内部路径连通，保留路径端点的 Balloon 高度为正

#### Scenario: Foreground components are separated by transparency
- **WHEN** 两个细结构之间存在透明间隙
- **THEN** 系统分别构建各自内部支撑，不跨透明间隙建立连接

### Requirement: Constraint validation uses the final mesh
系统 SHALL 在最终三角化结果中验证所需内部约束的实际边覆盖、连通性和内部顶点身份，SHALL 拒绝跨边界、穿孔洞、边界接触和丢失约束的结果。失败 SHALL 触发有效修复或明确错误。

#### Scenario: Simplified path would cross a hole
- **WHEN** 路径概括的候选线段穿过孔洞或碰到其边界
- **THEN** 系统使用有效内部路径重建该段，不能将候选线段直接送入最终网格

#### Scenario: Triangulation splits an input constraint
- **WHEN** CDT 将一条内部约束拆分为多个实际网格边
- **THEN** 系统验证这些边完整覆盖输入约束且首尾相接，而非要求输入边原样保留

#### Scenario: Short constraints at large pixel coordinates
- **WHEN** 高分辨率图片的短内部约束经 CDT 发生坐标舍入
- **THEN** 系统通过原始顶点和边映射验证实际约束链的端点连通，有效约束不因长度舍入误报；真实断线、被过滤的约束边和丢失端点仍报错

### Requirement: Ordinary interior sampling remains uniform
系统 SHALL 固定轮廓与稀疏内部路径、均匀化其余内部点，并以局部细分控制边界和内部的尺寸过渡。均匀化 SHALL 有确定的迭代上限和收敛停止条件。

#### Scenario: Broad cartoon region accompanies narrow appendages
- **WHEN** 卡通图像包含宽阔中央区域与细耳朵或细腿
- **THEN** 中央普通点保持接近目标间距，细部使用稀疏内部支撑；通过内部最近邻离散度和邻面尺寸比验收，不能只增加中央点数掩盖不均匀

### Requirement: Each creation uses its current inputs
系统 SHALL 在每次创建时根据当前像素、Selection、阈值和有效间距准备结构，计算期间复用分量内的几何查询数组。

#### Scenario: Detail or image pixels change
- **WHEN** 用户改变 Mesh Detail 或 Alpha 后再次创建
- **THEN** 系统从新输入重建轮廓与内部结构

### Requirement: Performance is measured with quality checks enabled
系统 SHALL 在四档密度下分别测量两种模式的数值构建与 Blender 创建，保留完整约束检查。基准 SHALL 使用相同已加载 Alpha、固定环境、预热和多次重复，并同时记录点数、轮廓误差、连通性与内存规模。

#### Scenario: Optimized implementation is accepted
- **WHEN** 正式实现进行性能验收
- **THEN** 四张基准图的几何质量通过，记录与原算法的耗时比较及复杂蕨叶的实际开销；首次生成计时包含过滤、轮廓、结构、布点、三角化和高度求解，精细模式不能通过静默切换原算法满足计时要求

#### Scenario: Large input reaches the resource limit
- **WHEN** 2K 或 4K 输入包含大量孔洞和独立区域
- **THEN** 系统验证网格上限、按分量的有界批次与峰值内存，不能使用小图或缓存计时替代该测量
