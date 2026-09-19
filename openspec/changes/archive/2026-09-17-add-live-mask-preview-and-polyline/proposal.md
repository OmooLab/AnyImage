## Why

Mask Brush 的实时 Image 预览在 4K 图片上会频繁上传大纹理，造成明显卡顿；红色填充 Overlay 还会随 Image 刷新时机出现或消失。Brush 更适合像 Lasso、Polyline 一样在手势期间只显示稳定的几何反馈，释放后再提交 Alpha 修改。与此同时，已删除的 Keep Original、Refine Selection 和 Invert 仍有测试或通用数据分支残留，Brush 还会为整条轨迹积累大量临时 Mask，适合在扩展 Gesture 时一并收紧。

## What Changes

- **BREAKING**：Mask Mode 默认值从 Set 改为 Subtract，使 Mask 默认表现为擦除 Alpha。
- Brush 按住拖动期间不读取或修改 Image Pixel Buffer；Overlay 与释放提交复用同一组圆形印记、连接条和 union 规则，急转与交错区域融合且虚线只保留融合后的外轮廓。显示沿用 Lasso、Polyline 的 Mode 填充：Subtract 为红色，Set/Add 为灰色。
- Mask Gesture 增加 Polyline，沿用逐点单击、移动预览、点击起点或 Enter 完成、Backspace 撤回一点的交互，并复用 Set、Add、Subtract Alpha 合成。
- 删除无生产调用方的 `SelectionPath.invert`、全画布反选栅格分支及旧字段序列化，清理只验证 Keep Original、Refine Selection 缺席的历史测试和测试参数。
- 删除由中心线偏移生成单一自交外框的方案，避免急转时 winding 产生三角孔洞；改为直接合并 Brush 圆和连接条。

## Capabilities

### New Capabilities

- `mask-editing`: 定义 Mask 的 Lasso、Brush、Polyline Gesture，Subtract 默认模式，Brush 虚线预览、释放提交与取消语义，以及无旧编辑状态的精简 Selection 数据边界。

### Modified Capabilities

## Impact

- 影响 `properties.py` 的 Mask 默认设置，以及 `operators/image_edit_tool/mask.py` 的释放提交与 Brush Selection 主链。
- 影响 `common/viewport.py` 的 Gesture 状态机、Polyline 与 Brush Overlay，以及 `common/selection.py` 的 SelectionPath 表示。
- 影响 Mask、Selection、Cutout、注册、交互与打包测试，并同步 Image Edit、Cutout 和 Common 内部文档。
- 不增加第三方依赖，不改变 Frame、Rectify、Cutout Shape、Remove Background 或 Server Job 协议。
