# cutout-edge-length Specification

## Purpose
TBD - created by archiving change use-world-space-cutout-edge-length. Update Purpose after archive.
## Requirements
### Requirement: Physical edge length control

系统 SHALL 提供正值浮点长度参数 Edge Length，初始物理默认值为 0.1 m，遵循 Blender 场景单位显示与换算。

#### Scenario: Default length
- **WHEN** 用户首次使用 Cutout
- **THEN** Edge Length 的初始值表示 0.1 m，并可连续调整

#### Scenario: Scene unit conversion
- **WHEN** 场景 Unit Scale 为 0.01，用户输入 0.1 m 且相对限制未触发
- **THEN** 建网目标间距为 10 个 Blender 世界单位

### Requirement: Relative spacing floor

系统 SHALL 在 Preferences 提供 Minimum Relative Edge Length 百分比，默认 1%，并使用 `max(请求边长, 有效裁切包围盒世界长边 × 最小比例)` 计算有效目标间距。包围盒 SHALL 来自参与建网的有效内容，包含所有组件，采用图像平面轴向边经过世界变换后的较长边。

#### Scenario: Floor is applied
- **WHEN** 包围盒长边为 1 m，最小比例为 1%，请求边长为 0.001 m
- **THEN** 有效目标间距为 0.01 m

#### Scenario: Requested spacing is retained
- **WHEN** 包围盒长边为 1 m，最小比例为 1%，请求边长为 0.1 m
- **THEN** 有效目标间距为 0.1 m

#### Scenario: Preference changes
- **WHEN** 用户将最小比例改为 2%，包围盒长边为 1 m，请求边长为 0.001 m
- **THEN** 有效目标间距为 0.02 m

### Requirement: Stable world density

系统 SHALL 根据有效世界间距驱动普通轮廓与 Fine Outline 的基础采样。图片分辨率与有效内容外的画布 SHALL 不参与目标间距定义；对象世界变换 SHALL 参与空间长度计算。

#### Scenario: Resolution and canvas changes
- **WHEN** 相同物理尺寸和轮廓的主体更换图像分辨率或增加透明画布，参数保持一致
- **THEN** 两种建网模式采用相同的有效目标间距

#### Scenario: Object scaling below the floor threshold
- **WHEN** 用户放大 Image Empty 且相对限制仍未触发
- **THEN** 目标边长保持一致，放大的区域获得更多采样点

#### Scenario: Rotation and nonuniform scale
- **WHEN** 对象旋转或非均匀缩放
- **THEN** 两种建网模式在世界平面度量中应用有效间距，旋转不改变包围盒长边基准

### Requirement: Detail preserving spacing semantics

系统 SHALL 将长度限制解释为基础采样目标，允许轮廓适配和三角剖分产生更短的边，并保持 Fine Outline 的细小部件支持。

#### Scenario: Thin outline feature
- **WHEN** Fine Outline 处理宽度小于有效间距的可用细小轮廓
- **THEN** 建网可增加局部采样并生成较短边，以保留该轮廓

### Requirement: Effective length feedback and parameter replacement

系统 SHALL 在相对限制生效后显示有效目标长度，并保留用户请求长度。系统 SHALL 使用新长度属性和相对偏好替换旧 Mesh Detail 枚举与最大网格分辨率设置。

#### Scenario: Visible clamp result
- **WHEN** 用户请求 0.1 m，但实际采用 0.2 m
- **THEN** 界面反馈显示有效长度 0.2 m，用户设置仍为 0.1 m

#### Scenario: Consistent execution paths
- **WHEN** 用户通过同步或 AI 异步路径生成 Cutout
- **THEN** 系统依据最终建网内容采用同一套有效边长规则

