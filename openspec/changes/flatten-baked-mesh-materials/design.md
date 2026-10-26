## Context

当前 Bake Mesh 固化支持的修改器前缀、保留单区 UV 或构建 Cutout Atlas，并通过临时 Diffuse BSDF 执行 Tangent Normal Bake。烘焙临时将 Normal Scale 设为 1、Bump Scale 设为 0，结果保留 O Image Layer。

O Image Layer 的实际输出为 Color、Roughness、Alpha、Normal、Specular。Color 直通，Roughness 使用 Float Curve，Alpha 使用带 Factor 的修正曲线，Specular 将颜色转为标量后 Clamp。当前工作区对颜色配置已有修改，实施以该工作区行为为准。

## Goals / Non-Goals

本次范围为 Bake Mesh 的静态结果：粗糙度、高光和完整法线效果成图，全部输出重接原消费者，删除结果材质中的 O Image Layer 实例。可编辑对象沿用现有资产和创建流程。

## Decisions

### 1. 按输出承接原连接

准备阶段记录节点组各输出的全部目标 socket。共享材质使用副本，独占材质暂存新增节点与原连线，全部图片写入成功后删除旧组实例；保留组外节点、未涉及连线和参数。

| 原输出 | 静态结果来源 |
| --- | --- |
| Color | 统一后的 0–1 sRGB Color，继续连接原消费者 |
| Roughness | 独立 Non-Color Roughness 图片 |
| Normal | 最终 Tangent Normal 图片 → 标准 Normal Map，Strength=1、UVMap |
| Alpha | 原 Alpha 来源 → 标准 Float Curve，复制曲线和 Alpha Fix；Factor=0 可直接接原 Alpha |
| Specular | 最终 Color 经标准 RGB to BW 后得到的独立 Non-Color PNG |

按实际输出连接承接，保留用户添加的组外处理。预检无法保证语义的自定义组内结构或输入连接，并在任何写入之前报告。Shadeless 沿用几何和 Color 固化路径。

### 2. 粗糙度与高光独立烘焙

先将源图片统一为 0–1 sRGB，再将临时材质 Color 输入替换为该单区图片。Roughness 使用原组曲线，Specular 使用标准 RGB to BW，接到临时 Emission，在现有隔离 Cycles 场景执行 EMIT Bake，直接取得 Blender 对当前颜色空间及曲线的求值结果。避免在 NumPy 中重复实现着色器颜色转标量和曲线采样。

先用浮点临时图取得线性结果，再截断到 0–1 并写入 8-bit Non-Color PNG 后 pack，避免直接向 byte 目标烘焙时发生 sRGB 编码。两个输出均使用最终 UV，尺寸为 Color 尺寸乘 Atlas 网格数。单区仍需生成 Roughness，相关输入必须满足静态采样条件。Color 保留 Alpha 及拼接方式，使用 8-bit sRGB PNG。inverse 和 HDR 复用固定 T=4、Gamma 0.75 归一化；普通 byte sRGB 和已归一化图片保持编码值，结果记录归一化标记。该步骤直接使用输入颜色空间，不读取偏好，也不修改共享节点组。

### 3. 固化最终法线，包含 Bump

复用现有 Diffuse NORMAL Bake 链路，以 O Image Layer 的最终 Normal 输出为源，保留当前 Normal Scale、Bump Scale、Object Space 和几何属性。源图片与 Tangent Normal Map 显式使用源 UV，目标写入最终 UV。

保留源 Normal 时的现有分辨率策略：Color 与 Normal 各维取较大值，再乘 Atlas 网格数。仅有 Bump 时按 Color 尺寸创建法线图。结果采用浮点 Non-Color、pack、Strength=1；源强度和 Bump 已被固化，不再叠加实时 Bump。

没有源 Normal 且 Bump Scale=0 时，直接使用标准 Geometry Normal 输出承接原法线消费者，省去空白法线贴图。存在源 Normal 时仍烘焙，以覆盖 Object Space、深度衰减和方向处理。

### 4. 发光与布局

读取原 Emission Strength：0 时删除 Emission Color 连接；大于 0 时复制最终 Color 内容为独立 `_emissioncolor` 图片，使用最终 sRGB Color 的颜色空间、Alpha 和精度，并保持强度单独作用。连接了动态强度的输入在预检中拒绝。

从 Principled BSDF 的输入顺序沿连接寻找图片节点，统一宽度并纵向等距排列，Normal Map 与法线图同排；失败时恢复原节点位置和宽度。

### 5. 提交与资源生命周期

先完成全部贴图和节点准备，再提交图片、节点及 Mesh；为原位材质节点修改准备完整恢复数据。失败恢复节点、连线、图片内容、Mesh、修改器及能力标记，并清理所有临时资源。测试分别注入 Roughness 烘焙、Normal 烘焙、图片写入和节点重接阶段失败。

无共享使用者的既有材质及 Color / Normal 保持身份、名称和路径；有其他使用者时沿用代码现有隔离规则。Roughness 及缺失的 Normal 为新增结果图片，使用 `_roughness`、`_normal` 分类，沿用当前按归属判断的参考图过滤。仅移除结果节点实例，共享 O Image Layer 数据块保留给其他对象。

## Risks / Trade-offs

- Bump 的屏幕导数效果与 UV 贴图采样可能存在差异 → 先用正负 Bump、非单位 Normal Scale 和旋转 symmetry 验证烘焙链路，使用固定光照与法线可视化比较。
- 原有侧壁 UV 退化或重叠限制独立细节 → 保留现有布局及近似边界，按有效 UV 面分类验证，不放宽正常表面阈值。
- 新增 Roughness Bake 增加耗时与内存 → 复用一次求值 Mesh 和隔离场景，按消费输出生成贴图并及时释放临时数据。
- 删除组实例扩大回滚范围 → 保留原组实例至提交末尾，异常时恢复原连线并移除新增节点；覆盖提交中途失败及 Undo / Redo。

## Migration Plan

更新 Bake Mesh 实现与相关测试，删除旧单位强度且跳过 Bump 的烘焙路径。运行相关 Blender 测试验证后交付；提案阶段仅新增本 change 的文件。若实施涉及节点资产修改，按项目规范构建、复制资产并运行相关节点测试。
