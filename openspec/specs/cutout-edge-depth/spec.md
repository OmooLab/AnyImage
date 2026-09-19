# cutout-edge-depth Specification

## Purpose
TBD - created by archiving change extend-cutout-edge-depth. Update Purpose after archive.
## Requirements
### Requirement: Reliable interior supplies edge depth

系统 SHALL 为包含透明内容的 Cutout 深度产物，从 Alpha ≥ 0.95、Validity > 0 且深度有限为正的候选域中，选择欧氏内缩 2 个深度图像素后的可靠核心。可见域 SHALL 继续使用 Alpha ≥ 0.1，核心深度 SHALL 逐值保留。

#### Scenario: Hair samples contain background depth
- **WHEN** 半透明毛发仍属于可见域，但其预测深度接近背景，所属分量存在可靠核心
- **THEN** 系统以该分量最近可靠核心的深度补齐毛发区域，并保留原颜色 Alpha 和裁切轮廓

#### Scenario: Subject reaches the image rectangle boundary
- **WHEN** 不透明主体延伸到图片矩形边界
- **THEN** 系统按边缘延续计算内缩，不将图片外部自动视为透明背景

### Requirement: Extension has deterministic component fallbacks

系统 SHALL 按可见域的 8 连通分量选择供体。缺少内缩核心时 SHALL 使用本分量未内缩的可靠候选；缺少可靠候选时 SHALL 保留该分量原始预测。

#### Scenario: Narrow component has no eroded core
- **WHEN** 细小分量的可靠候选在 2 px 内缩后消失
- **THEN** 系统使用该分量未内缩候选完成外延

#### Scenario: Translucent component has no reliable candidates
- **WHEN** 独立分量完全由低 Alpha 或模型无效像素组成
- **THEN** 系统保留该分量预测，不从另一可见分量复制深度

### Requirement: Filtered sampling uses extended depth

系统 SHALL 向可修复分量相邻透明区外扩 4 px 的范围延伸深度，并以 σ=0.8 px、半径 3 px 的 Gaussian 核仅平滑补齐区域。核心及其他未处理区域 SHALL 保留原值。

#### Scenario: Texture sampling straddles the silhouette
- **WHEN** 线性采样邻域跨越可见边缘和邻近透明背景
- **THEN** 透明侧提供外延深度，采样不会重新混入该邻域原来的背景深度

#### Scenario: Adjacent components have different depths
- **WHEN** 两个可见分量分别位于不同深度
- **THEN** 各分量的供体与平滑输入保持分量隔离

### Requirement: Corrected geometry preserves camera projection

系统 SHALL 根据修复后的 Z 和当前像素中心的相机射线重建 XYZ，使修复前后的相机投影保持一致，并保留核心原始 XYZ。

#### Scenario: Edge pixel inherits an interior depth
- **WHEN** 边缘像素采用另一像素的可靠 Z
- **THEN** 重建 XYZ 仍投影到边缘像素自身位置，而不是供体位置；数值测试的归一化投影误差 SHALL 小于 1e-6

### Requirement: Cutout artifacts share corrected depth

系统 SHALL 为 Depth Surface 与 Depth Balloon 的 Vector/Z Depth 和 Metadata 使用同一修复后深度。模型 Validity SHALL 保留其原始语义，Normal Writer SHALL 继续使用原始预测。

#### Scenario: Cutout exports vector depth and metadata
- **WHEN** Cutout 请求深度产物
- **THEN** Vector Depth 的 Z 与 Metadata 参考深度来自同一修复后深度场，所有输出坐标有限

#### Scenario: Existing artifact paths do not require correction
- **WHEN** 输入完全不透明，或请求来自普通 Depth Plane，或 Cutout 只生成 Normal
- **THEN** 系统使用对应的原始产物路径与预测行为

### Requirement: Edge correction is verified in the full Cutout pipeline

验收 SHALL 使用猫与人物原图依次执行 Remove Background 和 Cutout，固定同一 Alpha 与模型预测比较修复前后结果，并检查 Depth Surface、Depth Balloon 及 Normal 开关组合。

#### Scenario: Side-view regression comparison
- **WHEN** 两张实图完成完整 Blender 修改器求值
- **THEN** 主要边缘长条后缩明显减少，原 Alpha 可见域保持一致，可靠核心深度逐值不变，并记录残余台阶、着色或剔除问题

