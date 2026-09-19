## ADDED Requirements

### Requirement: Editable Quad Sphere surface

系统 SHALL 提供资产 `O Image Panorama`，使用全四边面 Quad Sphere，并提供 Subdivide、Depth Scale、Validity Threshold 和 Split Threshold。几何节点 SHALL 只有一个深度图片输入。

#### Scenario: Sphere and depth endpoints
- **WHEN** 所有样本有效且 Split Threshold 为 0
- **THEN** Subdivide=n 产生 6×4^n 个四边面，Depth Scale=0 为单位球，Depth Scale=1 为预测径向距离表面

#### Scenario: Validity culling
- **WHEN** 深度 EXR Alpha 低于 Validity Threshold
- **THEN** 按 Depth Plane 的点域布尔字段与面域删除方式剔除对应区域

### Requirement: Depth Plane split semantics

全景 SHALL 复用 Depth Plane 的相邻面深度差判断、内边分裂、面角深度重定位和条带面清理机制，并使用参考距离归一化的径向距离适配球面。

#### Scenario: Disabled splitting
- **WHEN** Split Threshold 为 0
- **THEN** 分裂与条带清理完全旁路，有效性剔除保持生效

#### Scenario: Foreground depth discontinuity
- **WHEN** 相邻有效面的归一化距离跳变达到分裂条件
- **THEN** 分离选中的内边，断层附近面角沿原球面射线使用所属面的距离，未选中顶点保持原始深度采样

#### Scenario: Threshold and scale consistency
- **WHEN** 增大 Split Threshold 或对所有距离与参考距离同时乘以相同正比例
- **THEN** 增大阈值不会减少被选中的断层边，等比例距离变化不会改变断层边选择

#### Scenario: Seam and strip cleanup
- **WHEN** 深度断层跨越全景经度接缝或分裂产生孤立条带
- **THEN** 经度接缝采用周期采样，面角 UV 保持正确，条带面按 Depth Plane 的同一拓扑快照规则清理

### Requirement: Packaged node assets

生产节点组及 Quad Sphere 子组 SHALL 包含在 `O_AnyImage.blend` 中，通过现有加载入口使用。

#### Scenario: Reopen converted object
- **WHEN** 在新 Blender 进程重新打开转换后的文件
- **THEN** 无需访问原型目录或外部参考库即可求值，贴图、细分、Depth Scale 和 Split Threshold 均正常工作
