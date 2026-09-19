# reference-depth-calibration Specification

## Purpose
TBD - created by archiving change unify-reference-depth. Update Purpose after archive.
## Requirements
### Requirement: Reference depth has one implementation
参考深度 SHALL 只由 `common/depth.py` 从 Depth 纹理计算。Server MUST NOT 计算或写出参考深度，`depth.json` SHALL 只包含 `image_size` 与 `intrinsics`。

#### Scenario: Write depth metadata
- **WHEN** Server 写出 `depth.json`
- **THEN** 文件包含 `image_size` 与 `intrinsics`
- **AND** 文件不包含 `reference_depth`

#### Scenario: Load depth artifacts
- **WHEN** Blender 加载 Depth 纹理与元数据
- **THEN** 参考深度由 Depth 纹理计算
- **AND** 元数据只提供相机内参与图像尺寸

### Requirement: Depth texture alpha and depth values define the reference domain
参考深度 SHALL 只统计同时满足 `Alpha > 0.95`、深度有限且深度大于零的像素。系统 MUST NOT 使用 Cutout 的 Alpha Threshold 或选区透明度比例参与该统计。

#### Scenario: Exclude transparent and invalid pixels
- **WHEN** 某像素的 Alpha 不大于 `0.95`，或相机 Z 非有限、非正
- **THEN** 该像素不参与参考深度统计

#### Scenario: Exclude semi-transparent source edges
- **WHEN** 源图 Alpha 与模型有效性的乘积落在 `0.5` 与 `0.95` 之间
- **THEN** 该像素不参与参考深度统计

#### Scenario: Exclude everything
- **WHEN** 没有任何像素满足有效条件
- **THEN** 参考深度取 `REFERENCE_DEPTH_BASELINE`

### Requirement: Reference depth uses the upper depth percentile
参考深度 SHALL 取有效像素相机 Z 的 95 百分位，并以模型单位返回。所有深度几何 SHALL 使用同一判据，MUST NOT 按目标区分统计量。

#### Scenario: Distant background is dropped before the percentile
- **WHEN** 部分有效像素的距离超过有效像素中位数的 `REFERENCE_DEPTH_RANGE_FACTOR` 倍
- **THEN** 这些像素不参与百分位统计
- **AND** 参考深度只由该范围内的像素决定

#### Scenario: Keep a distant subject
- **WHEN** 全部有效像素都远于 `REFERENCE_DEPTH_BASELINE`，但仍在自身中位数的 `REFERENCE_DEPTH_RANGE_FACTOR` 倍以内
- **THEN** 参考深度按这些像素的 95 百分位计算
- **AND** 主体不会因为基准落在自身之前而被钳制

#### Scenario: Depth distribution is skewed
- **WHEN** 有效深度在前后景之间分布不均
- **THEN** 参考深度取有效深度的 95 百分位
- **AND** 结果不小于同一深度场的中位数

#### Scenario: Share the reference across depth shapes
- **WHEN** 同一 Depth 纹理分别用于 Depth Plane、Relief Plane、Depth Solid 与 Depth Symmetry
- **THEN** 四者使用相同的有效域规则与相同的百分位

#### Scenario: Selection has little transparency
- **WHEN** 参考域内几乎没有透明像素
- **THEN** 系统仍按该参考域的有效像素计算 95 百分位
- **AND** 不使用固定基准值

### Requirement: Depth direction fits fall back to a flat plane
深度方向拟合 SHALL 在没有可用样本时返回无倾斜的规范方向，MUST NOT 报错。Relief Plane 与 Depth Symmetry 的 `Direction` SHALL 因此回退为 `(0, 0, 1)`，调用方 MUST NOT 各自实现兜底。

#### Scenario: Fit a relief without usable depth samples
- **WHEN** 深度图没有可参与拟合的有效像素
- **THEN** Relief Plane 仍成功创建
- **AND** `Depth Direction` 为 `(0, 0, 1)`

#### Scenario: Fit depth symmetry without usable samples
- **WHEN** 基础形状的采样点全部落在没有有效像素的区域
- **THEN** Depth Symmetry 仍成功创建
- **AND** `Direction` 为 `(0, 0, 1)`

### Requirement: Cutout scopes the reference depth to its selection
Cutout SHALL 把当前选区作为参考域传入参考深度计算，并额外要求像素位于该选区内。Plane 转换 SHALL 使用整幅 Depth 纹理作为参考域。

#### Scenario: Selection covers part of an opaque image
- **WHEN** 源图没有透明区域且用户只选中局部主体
- **THEN** 参考深度只统计选区内的有效像素

#### Scenario: Convert a whole image to a depth plane
- **WHEN** 用户把整幅图像转换为 Depth 或 Relief Plane
- **THEN** 参考深度统计整幅 Depth 纹理的有效像素

### Requirement: Reference depth anchors the uniform scale
参考深度 SHALL 作为 `Uniform Scale` 的归一化基准参与深度几何换算，MUST NOT 被预先乘以尺度。系统 MUST NOT 为参考深度新增用户参数。

#### Scenario: Convert model units to image plane units
- **WHEN** 系统创建深度几何
- **THEN** 参考深度以模型单位参与 `Uniform Scale` 计算
- **AND** 已缩放的参考深度写入 `Reference Depth` Modifier 输入

### Requirement: Alpha Threshold only controls the outline
Server MUST NOT 接收 Alpha Threshold 参数。Cutout 的 Alpha Threshold SHALL 只用于轮廓提取与内容有效性判定，MUST NOT 改变参考深度。

#### Scenario: Change alpha threshold
- **WHEN** 用户改变 Alpha Threshold 并重新生成深度几何
- **THEN** 轮廓按新阈值变化
- **AND** 参考深度保持不变

### Requirement: Relief Plane places its base plane by reference depth
`O Image Relief Plane` SHALL 使用默认值为 `0` 的 `Depth Offset`，基准平面由 95 百分位参考深度决定，`Depth Offset` 只保留微调职责。

#### Scenario: Create a relief plane
- **WHEN** 用户新建 Relief Plane
- **THEN** `Depth Offset` 为 `0`
- **AND** 基准平面位于参考深度

