## Why

Mask 保留了被剔除区域的 RGB，但后续 Frame 的预乘 Alpha 处理会丢失这些颜色，使用户再通过 Mask Add 恢复 Alpha 时无法找回图片内容。Frame 需要在透明结果中保留最底层图片的 RGB，同时保持前景渐变和既有 Alpha 合成。

## What Changes

- 对每个输出像素，以现有逐像素深度顺序中最底层的有效图片样本作为隐藏 RGB 来源。
- 以底层原始 RGB 打底，前景按自身 Alpha 连续混入底色，覆盖完全透明与半透明区域。
- RGB 与 Alpha 分开合成：前景使用预乘采样叠加到底色，Alpha 独立沿用原有 source-over；恢复 Alpha 后边缘保持渐变。
- 图片投射外的透明 Canvas 与现有边缘扩色继续保留；扩色仅填充没有有效源覆盖的透明区域。
- 补充单图 Mask → Frame → Mask Add、多图透明叠放、半透明混合和有效投影边界测试。

## Capabilities

### New Capabilities

- `frame-transparent-rgb`: 定义 Frame 透明像素的底层 RGB 来源、保留规则及其与 Alpha 合成、边缘扩色的关系。

### Modified Capabilities

无。

## Impact

- `src/anyimage/operators/image_edit_tool/frame.py`：保留原始颜色采样入口，复用当前深度排序和投影有效性，补全透明结果 RGB。
- `src/anyimage/common/image.py`：复用公共双线性采样与 RGBA 转换能力，保持其他调用方的现有结果。
- `tests/test_blender_addon.py`、`tests/test_cutout_objects.py`：像素计算及 Packed Image 编辑链路验证。
- 仅涉及 Blender 本地像素处理与测试；实施后运行测试，不构建文档或扩展包。
