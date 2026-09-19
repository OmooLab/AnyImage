## Why

同一前景图片通过“Remove Background 后生成 Depth Surface”和“原图启用 Fit to Foreground 后生成 Depth Surface”时，当前会向 MoGe-2 提交不同的隐藏 RGB，导致不同的 Mask 与 Depth 结果；Vector/Z Depth 又按有效 Mask 将 RGB 清零，使连续深度场在 Mask 边界退化到相机原点。与此同时，Depth 与 Normal 产物仍直接读取 MoGe-2 专用 Prediction，绕过了原本用于统一 MoGe-2 与 DA3 几何预测的 `GeometryFrame` 边界。

## What Changes

- 在最终 MoGe-2 推理入口统一将 RGBA 按 Alpha 合成到黑底；Alpha 为 `0.5` 的像素以一半原色、一半黑色进入模型，使 Remove Background 与 Fit to Foreground 工作流具有相同的输入语义。
- 以 MoGe-2 的单帧预测数据设计统一 `GeometryFrame`：包含 Depth、Normal、Validity、相机内参与可选 Points。Validity 统一承载 MoGe-2 的 `0/1` Mask 或 DA3 的连续 Confidence。
- MoGe-2 的生产推理直接返回 `GeometryFrame` 序列；DA3 保留原始 Debug Prediction，并提供到相同 `GeometryFrame` 的适配作为参考路径。
- Depth EXR、Normal Map 与 `depth.json` Writer 只消费 `GeometryFrame`，不直接读取 MoGe-2 Prediction 或模型专用字段。
- `vector-depth.exr` 的 RGB 对所有像素保存 MoGe-2 原始相机空间 XYZ，不再因 Validity 为零而写成零。
- `z-depth.exr` 的 RGB 对所有像素保存 MoGe-2 原始 Depth，不再因 Validity 为零而写成零。
- 两种 Depth EXR 的 Alpha 只保存模型原始 Validity，不与输入 Alpha、正深度检查或有限性检查合并。
- 非有限 Depth 或 XYZ 不进行静默替换；Artifact 生成明确失败，避免 NaN/Inf 进入 Blender Geometry Nodes。
- `GeometryFrame.validity` 是模型有效性信号的唯一事实；Depth Metadata 的参考深度按需组合输入 Alpha、Validity 与数值有效性，但不在 Frame 中保存第二套有效性字段。
- **BREAKING（内部产物语义）**：Depth EXR 中 Alpha 为零像素的 RGB 将从固定零值改为模型原始结果；依赖旧清零行为的内部消费者必须同步更新。

## Capabilities

### New Capabilities

- `moge-depth-artifacts`: 规定统一 `GeometryFrame`、MoGe-2 黑底输入以及 GeometryFrame 驱动的 Depth/Normal/Metadata 产物语义。

### Modified Capabilities

无。

## Impact

- 影响 `server/models/geometry.py`、`server/models/moge2.py`、`server/models/da3.py`、Geometry Writer 与其测试。
- Cutout Depth Surface 与 Convert to Depth Plane 将消费连续的 Depth RGB；现有 EXR 文件名、尺寸、通道布局和 Job 返回协议保持不变。
- 不改变 BEN2 模型、MoGe-2 模型、Blender Operator 标识符、节点组接口或外部依赖。
