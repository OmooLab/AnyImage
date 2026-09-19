## Why

本轮审查发现，图片读取会重载并覆盖 Blender 像素缓存，Frame 会误判有效透视交叠，Brush 的路径简化、覆盖合并和预览更新存在精度与性能问题。需要修复这些可复现行为，并清理同一调用链中的旧入口和重复计算。

## What Changes

- 让业务像素读取保持源 Image 的像素、Alpha 模式、脏状态与共享引用不变，保留已确认的结果 PREMUL 默认值。
- Frame 在齐次坐标中裁剪有效投射，再判断连续几何交叠。
- Brush 使用具有整段误差约束的屏幕路径；完整图元先合并覆盖，再统一抗锯齿。
- Brush 增量更新屏幕预览，复用填充与外轮廓的单一缓存。
- Mask 保留单步 Undo，移除没有 execute 实现的 REGISTER 与重做参数面板。
- Frame 直接输出独立合成的 RGB/Alpha，清理已被覆盖的预乘、反预乘与扩色处理。
- 将 Frame、Rectify 的矩形裁剪收敛到公共半平面裁剪；删除只供测试调用的转发函数和无消费者状态。

## Capabilities

### New Capabilities

- `image-pixel-read-integrity`: 业务像素读取的无副作用约束与脏缓存保留。
- `frame-projection-clipping`: Frame 连续有效交叠的齐次裁剪与合成输出约束。
- `brush-stroke-processing`: Brush 路径误差、覆盖合并、增量预览与 Mask 提交行为。

### Modified Capabilities

无。当前 `openspec/specs/` 为空；相关功能仍记录在未归档变更中。本提案补充其修复契约，实施以当前工作区为基线，与 `enable-image-alpha-blending-and-premul`、`support-frame-view-plane-intersections`、`add-live-mask-preview-and-polyline`、`preserve-frame-bottom-layer-rgb` 共同验收。

## Impact

- `common/image.py`：像素读取及结果数据保留。
- `common/selection.py`、`common/viewport.py`：裁剪、路径、覆盖和预览缓存。
- `operators/image_edit_tool/frame.py`、`mask.py`、`rectify.py`：交叠、提交与共享能力调用。
- Cutout Lasso 作为公共手势消费者参加回归验证；轴向与节点资产沿用当前实现。
- 增补行为回归与结构性性能测试，运行全量 pytest；实施仅修改代码和测试，不增加依赖、不构建文档或发布产物。
