## Context

可编辑 Cutout 使用单区图片和完整源 UV。几何节点维护实时形状、法线属性及表面区域；专用 Convert to Mesh 负责最终贴图布局和静态结果。

`O Image Layer` 消费 `o_normal_reduction`、`o_depth_rotation`、`o_depth_face`、`o_depth_axis`，实现强度、坐标旋转、镜像及 wall 禁用。法线固化必须以这些处理后的表面法线为依据；只修改贴图通道不足以消除属性依赖。

本变更直接替代 `split-cutout-front-back-uv` 尚未归档的实现协议。

## Goals / Non-Goals

**Goals:**

- 可编辑 Cutout 使用单图及源 UV，Geometry Nodes 保持实时形状和着色。
- 转换时生成独立纹理地址和静态法线，最终结果只依赖普通 Mesh、UV、图片与材质。
- 删除旧创建阶段拼接代码及其调用、专用变换和过时测试。
- 转换后清除 AnyImage 形状、法线、来源及临时属性，保留用户数据。
- 保留现有材质结构和共享 `O Image Layer`，有效 UV 表面的外观在量化与采样容差内一致；退化侧壁 UV 保持简单映射及可接受的近似。

**Non-Goals:**

- 支持项目生成的 Plane、Depth Plane、Relief Plane、Panorama、Cutout 及一次 Cutout Symmetry；任意用户节点、任意修改器组合、重复 symmetry 和通用材质烘焙不属于支持范围。
- 本变更不增加 AI 背面生成，也不迁移已有旧双区 `.blend` 对象。

## Decisions

### 1. 单图编辑与静态转换分离

Color、Normal、Depth 在创建时保持各自产物尺寸的单区图片。基础 `UVMap` 使用完整 0–1 坐标；Rear 与 mirrored 通过共享源采样位置显示同一图像。Boundary Padding 继续处理单区 Color 与 Depth。

移除 `cutout_tool/texture.py` 的旧创建期拼接入口、`_assign_uv()` 的上区变换、`move_uv_to_lower_tile()`、`source_depth_uv()` 的 Atlas 逆变换及所有对应调用。Depth 的独立采样边界保护如仍必要，应保留在职责明确的采样入口，不以旧函数转发形式存在。单图 Tangent Normal 的后片着色应验证与当前默认双区图等价。

普通 Cutout 为旧 Atlas 增加的中圈及分支逐项检查；仅为旧布局服务的构造删除，仍用于几何闭合或最终表面分界的拓扑需有具体消费者。Depth Cutout 的侧环塑形保留其几何职责。转换期的布局和图片代码集中于新转换模块。

### 2. 由表面来源建立最终区域

节点在构造位置写入公开的 FACE/INT `o_image_region`，作为转换消费者的输入。Front、Rear、retained、mirrored 形成最多四种主要组合；Symmetry 必须传播既有 Front/Rear 来源，不能用着色用的 `o_depth_face` 覆盖它。

布局的纵轴表示正反面（上正、下背），横轴表示本体与镜像体（左本体、右镜像）。完整四区为左上 0、左下 1、右上 2、右下 3；仅正反面时上下排列，仅本体与镜像正面时左右排列。完全缺失的行或列可省略，局部缺失的组合留空，保留坐标轴语义。

最终 CORNER UV 保持源形状，只进行 tile 缩放、偏移及水平翻转。背面与镜像体各叠加一次翻转，因此区域 1、2 水平翻转，区域 0、3 保持原方向。Color 同步翻转，保证原表面颜色采样对应不变；静态法线直接烘焙到翻转后的目标 UV。Side 和 fill 继承所属区域及既有 UV，退化 UV 的侧壁法线仍是已知近似限制。

Color 每个 tile 保持源图尺寸并逐像素复制，保留透明 RGB、Alpha 与 HDR。Normal 的 tile 尺寸采用 Color/Normal 逐轴最大值，与 Color 共用归一化布局。

### 3. 将实际法线效果烘焙成 Tangent Normal

采用同一份当前求值 Mesh，同时保存源 UV 和最终目标 UV。临时材质中的图片及 Tangent Normal 节点显式读取源 UV，Cycles CPU NORMAL Bake 写入目标 UV，并采用临时 Diffuse BSDF 的 Normal 接收 O Image Layer 法线输出。原型验证 Principled 的反射有效性修正会改变背面法线，Diffuse 路径则与原始法线输出匹配。临时烘焙材质将 Normal Scale 设为 1；烘焙包含 Depth Scale、Balloon 衰减、Rear/Side 禁用、symmetry 旋转和接缝衰减。

同 Mesh 的直接烘焙关闭 selected-to-active；每个目标像素直接对应所在面，不使用跨对象射线投射。临时场景和材质隔离渲染状态，临时对象使用原对象矩阵。转换同步阻塞执行，完成或失败后恢复用户场景并清理临时数据。

Color 按区域直接复制和水平翻转，保留 RGB、Alpha、HDR/编码解释。Normal 使用 Non-Color、明确的切线通道约定，保存与重载保持有效。具有有效 UV 面积的表面记录其实际法线效果；退化侧壁沿原 UV 采样静态图，不能独立表达多个表面法线。

保留材质中的 Bump Scale 及其颜色派生效果。法线烘焙源取 Bump 之前的 Normal Map 结果，避免在最终材质中重复叠加 Bump。若无有效 Normal 输入，按实际需要跳过法线图生成。

### 4. 保留材质结构，只切换静态输入

转换目标保留原有材质节点、`O Image Layer`、Alpha Fix、粗糙度与其他连接。原材质的 Normal 输入替换为单位强度烘焙图，Color 输入替换为静态 Atlas，`Object Space=false`。Normal Scale、Bump Scale 及其他材质设置保持原值。Object/Tangent 模式的非单位强度计算并不完全等价，强度作为转换后材质的实时参数保留。

共享 `O Image Layer` 不因单个对象转换而修改。结果没有 `o_normal_reduction` 时使用现有单位权重默认值，Tangent 路径不会使用对象空间旋转属性。删除法线属性后继续验证外观，不能仅凭节点未报错判断正确。

结果直接引用原材质与原图片数据块，图片名称、路径和节点引用保持不变，原位更新图片尺寸与内容。共享图片的其他使用者同步看到更新，共享材质的其他对象也会看到 Object Space 更新；共享节点组本身不修改。临时烘焙材质与图片在结束时清理。不需要法线图的对象跳过烘焙；需要固化法线但没有现成 Normal 图片、或 Color/Normal 共用同一图片时，转换前明确拒绝。

### 5. 完成后清除程序化数据

转换器消费完数据后，按项目维护的准确属性清单清除 `o_balloon`、`o_normal_reduction`、`o_depth_rotation`、`o_depth_face`、`o_depth_axis`、`o_image_region` 及本次仍存在的 AnyImage 中间属性，同时清除对象或 Mesh 上的 AnyImage 程序化元数据。已消费的临时 UV 层和烘焙标记一起删除。

保留最终 `UVMap`、网格必要的 position / topology / material index / smooth / sharp 数据、用户自有属性和 UV 层。不能用“删除所有 attributes”破坏网格，也不能按宽泛 `o_*` 前缀误删用户数据。`o_image_object` 能力标记保留，因为其消费者是图片操作菜单，不表示存在 Geometry Nodes；重复转换通过支持的节点栈及来源协议识别并拒绝。

实时对象仍需要法线属性供材质读取，清理发生在静态结果提交前。这与“转换后没有任何 AnyImage 形状、法线、区域属性”的要求一致。

### 6. 原位、事务式转换

`ConvertToMesh` / `anyimage.convert_to_mesh` 从 AnyImage 对象菜单操作活动图片对象，支持完整可识别的项目节点栈。额外修改器、未知材质连接、Cutout 缺失区域协议或旧双区对象在修改数据之前明确拒绝。

先在隔离临时数据上完成求值、布局、图片生成和校验，完成所有构建后原位更新图片内容、替换对象 Mesh 并移除已求值 Modifier，保留对象身份、变换、集合和用户自有属性。提交前保存图片内容，失败恢复原图并释放临时资源，原对象保持可编辑；成功支持 Undo / Redo。临时烘焙场景及渲染设置不泄露到用户场景。

### 7. Convert To 单区对象及 Depth 生命周期

Plane、Depth Plane、Relief Plane 和 Panorama 保留求值 Mesh 的单区 UV 与 Color 内容。普通 Plane 默认无 Normal；Panorama 保留自发光材质及 REPEAT 采样。Depth Plane 的 Object Space 法线转换为 Tangent，Relief Plane 的 Depth Scale 和边界衰减烘入单位强度法线图；两者均保留原 Normal 图片身份与材质强度，随后清理法线协议属性。

所有转换在提交前收集修改器 `Depth Image` 输入，成功移除修改器后，仅删除其中用户数为零的图片数据块。材质、其他修改器及 Fake User 的引用受到保护，磁盘文件保持原样；撤销可恢复图片和修改器。

## Risks / Trade-offs

- [复制 tile 无法表达侧壁不同的空间法线] → 保留简单 UV；退化侧壁的静态法线误差单独记录，不能承诺完全匹配。
- [薄壳烘焙串面或色彩解释变化] → 原型覆盖非对称颜色、非平坦法线、薄壳及 HDR；对比转换前后法线通道和固定光照渲染。
- [纹理烘焙是有损采样] → Color 逐像素拼接；Normal 按源分辨率烘焙并验证表面内部误差。
- [属性清理漏项或破坏用户数据] → 显式清单加静态结果检查，测试用户自定义属性和额外 UV 的保留。
- [原生烘焙引入运行时间] → 无 Normal 的对象跳过法线烘焙及临时材质复制，其余同步执行。

## Migration Plan

1. 验证静态法线烘焙与简单区域布局，固定有效 UV 表面的误差阈值及退化 UV 的行为约束。
2. 替换创建阶段协议、补足面来源标记，删除旧代码和过时测试，不建立兼容开关。
3. 实现转换、菜单、注册、事务和清理，完成相关测试与节点资产重建验证。
4. 与 `split-cutout-front-back-uv` 的归档协调：先归档该旧变更，再应用本变更提供的移除/修改 delta，废止 `cutout-double-sided-textures` 和创建期 Atlas 要求。两个变更保留历史记录，实施完成不自动归档。

## Open Questions

无。

## Validation

- Tangent Normal 使用 Normal Scale=0.6，Object Normal 使用单位强度作为空间转换基准；Bump Scale=0/0.08、对象旋转与非均匀缩放均参与渲染对比。有效 UV 表面的内部像素法线编码 RGB 向量误差 95% 分位小于 0.04，固定光照线性 RGB 的阈值为 0.06。
- 普通 Shell 通过相机射线获取可见面，以 UV 三角形面积分类，独立于渲染颜色筛选有效覆盖；转换前后可见面分类须一致。退化侧壁必须仍可见且渲染值有限，其原有 UV 关系保留。表面边界剔除 2–4 像素以隔离抗锯齿。
- Depth Symmetry 覆盖非默认 Direction、Depth Scale=0.5、Smooth=2、零厚度与 Shell Thickness=0.15，验证左右双区/完整四区及全部协议属性清理后的渲染。
- 单区、上下双区、左右双区、四区及缺失组合分别验证 UV 缩放、区域位置与双重水平翻转。Color 拼接包含 HDR、透明 RGB 和 Alpha，要求逐像素相等；byte/sRGB 与 float/Non-Color 图片打包重载保持原值。
- 同步菜单调用与直接执行均验证 Undo/Redo、共享材质原位更新。缺失/保留 UV 名称冲突、额外修改器、链接 Normal Scale 在烘焙前失败；场景初始化、图片分配、烘焙失败均验证资源释放与用户场景恢复。
- 分别以 Normal Scale=0、0.3、1、2 转换，烘焙法线像素必须完全相同；原材质身份、共享节点组、所有非 Object Space 输入保持不变。
