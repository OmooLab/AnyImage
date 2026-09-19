## Why

高清图片提交 Image Tool 或 Cutout 选区时，当前主线程会重复读取整图像素、栅格化 Selection 并扫描 Alpha；Cutout 甚至在 Shape Pie Menu 打开前就完成一轮像素处理，导致未启用 AI 也出现明显卡顿。选区数据应在用户真正提交操作后只生成一次，并由后续步骤直接复用。

## What Changes

- Image Tool 与 Cutout Tool 复用同一条 Viewport 手势主链，只负责从手势构建一次内存中的 `SelectionPath`，不在用户圈选阶段执行 JSON 往返、读取图片或构建 `SelectionMask`。
- Image Tool 由同一个 Operator 在实际图片编辑阶段直接消费内存中的 `SelectionPath`，删除 `selection_path_json` Property，并在该阶段才构建一次 `SelectionMask`。
- Cutout 手势完成和双击全选将内存中的 `SelectionPath` 交给 Shape Pie Menu；菜单仅为跨 Operator 传值调用一次 `to_json()`，`CutoutSelectionToShape` 从按钮 Property 接收该值，不引入令牌、缓存或额外 Selection 生命周期。
- Cutout 在用户选定 Shape、实际执行生成时才把 `SelectionPath` 转换为一次 `SelectionMask`，并复用结果完成可见性检查、本地 Shape 创建或 AI 输入准备。
- 增加调用次数与高分辨率选区测试，确保菜单前零像素处理、提交后单次处理，并同步内部文档。

## Capabilities

### New Capabilities

- `image-selection-processing`: 规定 Image Tool 与 Cutout 对 Selection Path、Selection Mask 和源图像素的单次处理时机与复用行为。

### Modified Capabilities

无。

## Impact

- 影响 `common/selection.py`、`common/image.py`、Image Tool、Cutout Tool 的交互与转换主链，以及相关测试和内部文档。
- Image Tool 与 Cutout 圈选 Operator 不再保存 `selection_path_json`；Cutout Pie Menu 到 `CutoutSelectionToShape` 的跨 Operator 边界继续通过 String Property 传递 Selection Path JSON。
- 不改变用户界面、Shape 候选项、AI Job 协议或最终图像与几何结果。
- 不新增依赖；Image Tool 与圈选 Operator 的旧 Selection JSON 路径不保留兼容入口，Cutout Shape Operator 所需的跨 Operator JSON 传值继续保留。
