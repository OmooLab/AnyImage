## Why

Cutout 的材质和深度在网格轮廓处会线性混合轮廓外的不稳定像素。移动共享 UV 会同时扭曲多个纹理消费者；按最近 donor 搜索又会在复杂轮廓处产生不确定方向，因此需要在 Cutout 客户端按唯一的结构内向统一延伸边界纹理。

## What Changes

- 服务端停止 Cutout 专用深度延伸，只输出未经边缘处理的 MoGe Depth、Metadata 与 Normal；MoGe 输入保持原样。
- Cutout 客户端从最终 Mask 建立局部结构 inward mapping，以固定方向从轮廓内采样，并同时处理独立材质 RGBA 与 Depth。
- 材质搬运完整 RGBA；Depth 搬运 camera Z 与 validity，并使用目标像素和原始 intrinsics 重建 camera X/Y。
- Preferences 的 Cutout Tool 增加 `Boundary Padding`，默认 2 px、范围 1–4 px；同一数值同时表示内部采样距离和外部延伸宽度。
- 保持源 Image、网格几何、UV、Normal 与原始 Depth Metadata 标定不变。

## Capabilities

### New Capabilities

- `cutout-boundary-padding`: 规定 Cutout 客户端对材质和深度使用同一结构内向映射的边界延伸、设置与数据隔离。

### Modified Capabilities


## Impact

- `src/anyimage/operators/cutout_tool` 的最终 Mask、颜色图和深度图处理及对象创建路径。
- `src/anyimage/operators/cutout_tool` 中的图片缓冲读写与目标射线 Depth 重建。
- `src/anyimage/preferences.py` 的 Cutout Tool 设置。
- `src/anyimage/server/jobs/cutout.py` 与 `server/geometry/prediction_artifacts.py` 移除 Cutout 深度延伸启用路径；无节点资产变化。
- Cutout padding、深度投影、同步/异步路径、Preferences 和资源生命周期测试。
