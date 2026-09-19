## ADDED Requirements

### Requirement: Depth has one file contract

系统 SHALL 将所有深度图片写为 `depth.exr`，通过结果键 `depth` 返回。文件 MUST 使用 RGBA float32，RGB 为相机 XYZ，Alpha 为有效性，并沿用相机坐标、像素方向和非有限值处理约定。内部标量深度和 `depth.json` SHALL 保留。

#### Scenario: Generate depth artifacts
- **WHEN** 整图转换、Depth Solid 或 Depth Balloon 请求深度
- **THEN** 结果包含 `depth` 与 `depth_metadata`，对应 `depth.exr` 和 `depth.json`
- **AND** 不生成 `z-depth.exr`、`vector-depth.exr` 或旧结果键

#### Scenario: Preserve independent channels
- **WHEN** 输出合成数据中 X、Y、Z 不同的深度图
- **THEN** 解码后的 RGB 分别保持 XYZ 数值和有效性，不将 Z 复制到 RGB

### Requirement: Depth generation is a boolean request

共享产物生成 SHALL 使用布尔 `generate_depth` 决定是否生成深度，法线请求保持独立；深度消费者 SHALL 请求保留 XYZ 的单次推理，并沿用现有边缘深度修正条件。

#### Scenario: Generate depth and normals together
- **WHEN** 同时请求深度和法线
- **THEN** 只运行一次预测，生成统一深度、元数据和请求的法线产物

#### Scenario: Generate normals alone
- **WHEN** generate_depth 为 false 且请求法线
- **THEN** 生成法线，不写出深度图片或深度元数据

### Requirement: All consumers use the unified channels

整图与 Cutout 结果加载器 SHALL 从 `depth` 加载深度并沿用 Pack、数据色彩空间及尺度标定。Camera 与 Depth Cutout SHALL 读取 XYZ；Relief、Depth Balloon 和公共标量深度读取函数 SHALL 读取 B/Z。

#### Scenario: Scalar depth is distinct from X
- **WHEN** X 与 Z 明显不同的纹理用于 Relief 或 Depth Balloon
- **THEN** 几何位移由 Z 决定，效果与使用相同标量 Z 的现有结果一致

#### Scenario: Projected geometry keeps camera coordinates
- **WHEN** 统一深度纹理用于 Camera 或 Depth Cutout
- **THEN** 投影位置、有效性和尺度与更名前的 XYZ 输入一致
