## Why

全景原型已验证 Quad Sphere、径向深度和单张深度 EXR 的可行性。现在需要把生成流程接入 Image Empty 的常用入口，并通过 Depth Plane 的 Split Threshold 机制处理前后景连接处的拉伸。

## What Changes

- 在 Image Empty 的 AnyImage 右键菜单增加 `Convert to Panorama`，通过后台 Job 将静态 2:1 全景转换成可编辑的全景表面。
- 将原型的多视图 MoGe2 推理、距离融合和深度 Alpha 导出接入正式 Server。
- 新增 `O Image Panorama` 节点资产，提供 Quad Sphere 细分、Depth Scale、Validity Threshold 和 Split Threshold。
- 复用 Depth Plane 的分边、面角深度重定位和条带面清理机制，按全景径向距离适配判断。
- 延续单深度图片输入：`depth.exr` 的 Alpha 在导出时合成模型 Mask 与当前源图 Alpha。

## Capabilities

### New Capabilities

- `panorama-conversion`: Image Empty 菜单、异步转换、对象替换与撤销。
- `panorama-geometry-generation`: 全景多视图推理、融合与文件产物。
- `panorama-surface`: Quad Sphere、球面 UV、深度有效性剔除与 Split Threshold。

### Modified Capabilities

## Impact

涉及 `menu.py`、类型注册、新增 `operators/convert_to_panorama/`、Server Job 与全景几何模块、共享深度表面节点构建函数，以及对应测试。生产节点组由资产构建流程写入 `O_AnyImage.blend`，运行时按名称加载。使用现有 MoGe2、ONNX Runtime、NumPy 与 SciPy 环境。
