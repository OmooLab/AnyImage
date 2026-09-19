## Why

透明图合成黑底后交给 MoGe2，会改变天空等背景及轮廓附近的 RGB，影响场景深度预测。Depth Plane 需要同时按原图覆盖范围和模型有效性剔除，Cutout 则需要稳定的 alpha 轮廓深度。

## What Changes

- MoGe2 输入先读取 RGB 再缩放，保留透明像素下的颜色。
- 深度延伸以原图 alpha 轮廓确定范围，模型 mask 用于筛选可靠来源。
- `GeometryFrame.validity` 保持模型 mask；导出 `depth.exr` 时 Alpha 为原图 alpha 与 validity 的乘积，RGB 保存延伸后的相机空间 XYZ。
- Depth Plane 通过现有 Valid Only 与 Validity Threshold 消费 EXR Alpha；Cutout 继续按自身轮廓生成几何。

## Capabilities

### New Capabilities

- `depth-alpha-semantics`: 定义 MoGe2 RGB 输入、alpha 轮廓延伸以及深度产物有效性通道。

### Modified Capabilities

## Impact

- 涉及 `server/geometry/prediction_artifacts.py`、`edge_depth.py`、`depth_texture.py` 及对应调用与测试。
- 检查 Depth Plane、Cutout、Relief Plane 对共享深度产物的消费，包括校准用途。
- 接续工作区已有 Depth Plane 与 Relief Plane 拆分实现，采用当前节点阈值和剔除规则。
- 深度产物需重新生成以获得新 Alpha 语义。实现只运行测试，不同步内部文档或构建节点资产、扩展包；无新增依赖。
