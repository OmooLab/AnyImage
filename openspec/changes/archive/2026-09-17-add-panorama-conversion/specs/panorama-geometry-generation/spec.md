## ADDED Requirements

### Requirement: Generate panoramic radial distance

Server SHALL 从当前 RGBA 全景生成 12 个重叠的 90 度透视视图，使用已知 FOV 恢复 MoGe2 几何并融合为横向周期的径向距离场。

#### Scenario: Continuous panorama
- **WHEN** 输入包含跨越 U=0/1 的连续表面
- **THEN** 两侧使用同一周期求解，产出有限正距离且无额外拼接断层

#### Scenario: Invalid views and cancellation
- **WHEN** 部分视图全透明或模型无有效预测
- **THEN** 利用其余有效观测完成融合，全局无有效几何时返回明确错误，并在视图与融合阶段响应取消

### Requirement: Export combined depth alpha

系统 SHALL 返回颜色文件、`depth.exr` 与 `depth.json`。深度 RGB 保存径向距离，Alpha 在导出时一次合成融合 Mask × 源 Alpha；元数据 SHALL 标明等距柱状投影、深度图尺寸和参考距离。

#### Scenario: Transparent background
- **WHEN** 源图某区域 Alpha 为零
- **THEN** 该区域深度 EXR Alpha 为零，颜色文件保留源 Alpha

#### Scenario: Fractional alpha
- **WHEN** 有效模型 Mask 为 1 且源 Alpha 为 0.5
- **THEN** 深度导出 Alpha 为 0.5，几何端直接消费该值

### Requirement: Use managed production runtime

全景生成 SHALL 使用现有模型会话、Preferences 配置和 Job 生命周期；Job 参数可序列化，Server 与 Blender 数据保持进程边界。

#### Scenario: Configured inference
- **WHEN** 用户修改模型或推理分辨率级别后发起转换
- **THEN** 新任务采用配置值，最终网格细分仍由独立 Subdivide 参数控制
