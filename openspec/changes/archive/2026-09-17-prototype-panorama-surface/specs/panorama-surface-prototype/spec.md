## ADDED Requirements

### Requirement: Isolated panorama experiment

试验 SHALL 将代码和输出保存在独立试验目录，使用已有模型及运行环境。

#### Scenario: Run prototype
- **WHEN** 执行全景原型
- **THEN** 生成距离数据、独立 Blender 文件与验证结果，原有源码及节点资产保持原状

### Requirement: Periodic distance reconstruction

试验 SHALL 对完整全景使用周期经度映射、多视图距离融合及已知 90 度相机视角。

#### Scenario: Synthetic reference
- **WHEN** 使用解析球面或房间距离验证
- **THEN** 投影与融合产生有限正距离，并记录与真值的误差

### Requirement: Geometry node surface

试验 SHALL 使用可调 Subdivide 的 Quad Sphere，按全景距离沿球面射线定位顶点。Depth Scale 为 0 时保持单位球，1 时恢复预测距离。深度导出 SHALL 将 Mask × 源图 Alpha 写入 depth.exr 的 Alpha；几何节点 SHALL 只接收一张深度图片，并按该 Alpha 与 Validity Threshold 的比较结果剔除无效面。

#### Scenario: Reload Blender asset
- **WHEN** 在新的 Blender 进程加载试验文件
- **THEN** 全有效输入下网格闭合且仅有四边面，面数为 6 × 4^Subdivide，Depth Scale 0 与 1 分别得到单位球和预测表面

#### Scenario: Invalid image samples
- **WHEN** 输入包含无效 Mask 或透明图片 Alpha
- **THEN** 按 O Image Depth Plane 的点域布尔选择与面域删除方式剔除不合格区域

#### Scenario: Sky removal before geometry prediction
- **WHEN** 生成真实全景照片示例
- **THEN** 先去除天空背景，使用处理后的透明全景进行几何预测与深度导出
