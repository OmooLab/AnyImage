## Why

BEN2 通过普通 RGB 图像预测前景透明度。当前去背景流程用 Pillow 合成并保存 PNG，无法保留 HDR 图像的浮点颜色。将识别预览与原始颜色分离，可以让用户对 HDR 图片去背景，同时保留用于渲染的亮度和色彩。

## What Changes

- 为 Remove Background 增加 HDR 静态图处理，覆盖 Blender 已加载的 EXR、Radiance HDR、已打包及生成的浮点图片。
- 从提交时的浮点像素生成经过固定色调映射的 RGB 识别预览，原始颜色留在 Blender 侧。
- BEN2 提供浮点 alpha 结果；主线程将其与源 alpha 相乘，并与原始颜色合成。
- 结果使用 32-bit float RGBA EXR 持久化，支持保存重开、共享图片隔离、撤销和失败恢复。
- 对 HDR 动画输入在准备阶段给出明确提示；普通图片与现有视频、序列沿用当前行为。

## Capabilities

### New Capabilities
- `hdr-background-removal`: HDR 静态图片的识别预览、alpha 预测、浮点结果及生命周期。

### Modified Capabilities

无已发布能力规格需要修改；与现有 ImageEditTarget 的目标提交语义衔接。

## Impact

- Blender：`common/image.py`、`common/image_target.py`、`operators/remove_background.py`；复杂的 HDR 图像处理可独立放入 `common/hdr_image.py`。
- 后端：`server/models/onnx_ben2.py`、`server/models/ben2.py`、`server/jobs/remove_background.py`，以及对应测试。
- 输入仍为普通预览 PNG，新增 Job 的 alpha 产物模式，复用 NumPy 保存数值结果。BEN2 权重与运行依赖保持现有配置。
- 与进行中的 `unify-ai-input-validation` 及图片目标编辑变更共同使用实施时的真实调用链。
