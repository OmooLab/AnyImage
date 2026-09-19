## ADDED Requirements

### Requirement: Object Space Normal follows the canonical object frame

系统 SHALL 让 Plane、Depth Plane、Relief Plane、Cutout 与 Depth Cutout 的 Object Space Normal 贴图按新的 canonical Blender 对象坐标解释：X 为图片水平、Z 为 up、Y 为深度方向。Object Space Normal 渲染结果 MUST 与最终 evaluated geometry 的几何法线方向一致。

#### Scenario: Depth object uses Object Space Normal

- **WHEN** Depth Plane 或 Depth Solid 使用 Object Space Normal 贴图渲染
- **THEN** 平面法线朝向 -Y
- **AND** 深度表面产生的 normal 变化围绕 -Y 基准
- **AND** 渲染 normal 不再按旧 `-Z` 基准解释

### Requirement: Depth Symmetry normal maps follow mirror and final orientation

`O Image Cutout Symmetry` SHALL 为 Object Space Normal 提供最终朝向所需的面属性。材质 SHALL 对 canonical front 保持 normal，对 canonical back 反射 Y 分量，并应用最终 yaw 旋转；侧壁 SHALL 关闭 normal map 影响。

#### Scenario: Front, back, and wall normals

- **WHEN** Depth Symmetry 对象启用 Object Space Normal 并分别渲染 front、back 和 side wall
- **THEN** front normal 按 canonical 方向解释
- **AND** back normal 的 Y 分量相对 front 发生反射
- **AND** 最终 X 朝向旋转被应用
- **AND** side wall 不显示 Object Space Normal 细节

### Requirement: Old Depth Axis normal compensation is removed

材质和 normal-map 辅助代码 MUST 不再为 `O Image Cutout` 或 `O Image Depth Cutout` 的旧 `Depth Axis=+X` 提供 `CUTOUT_Z_TO_X` 补偿。Object Normal 的最终轴向转换 SHALL 只来自 Depth Symmetry 的新朝向属性。

#### Scenario: Inspect normal transform attributes

- **WHEN** 检查 `O Image Layer` 使用的 Object Normal 转换逻辑
- **THEN** 不存在以旧 `Depth Axis` 为输入的轴向补偿
- **AND** Depth Symmetry 的最终朝向属性由 `O Image Cutout Symmetry` 写入
- **AND** 材质按该属性执行最终 normal 旋转
