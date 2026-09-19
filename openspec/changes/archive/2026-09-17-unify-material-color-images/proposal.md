## Why

材质直接复用原 Image 会让再次导入原文件或再次粘贴剪贴板内容带入材质配置及绘制结果。Cutout 与 Convert To 需要统一的独立颜色图流程，剪贴板缓存则需要确认当前图像仍代表最初粘贴的内容。

## What Changes

- Cutout、Plane、Depth Plane、Relief Plane、Panorama 和剪贴板 Plane 统一按图片范围生成材质颜色图：导出独立临时文件、独立加载、以 `_color` 命名、配置并打包。
- Cutout 始终使用裁切范围；Convert To 和剪贴板 Plane 使用整图范围。是否使用 AI 只影响深度、法线等推理产物。
- 材质颜色图与原 Image、原文件加载路径及剪贴板缓存标记隔离，保留源像素精度和各入口的颜色空间、Alpha 规则。
- 普通 byte 图继续场景视图适配；所有 float / HDR 保留源解释，无法无损往返的输入明确拒绝转换。
- 保留相同剪贴板内容的复用；缓存命中时核对当前像素、尺寸、颜色空间和 Alpha 模式，修改后的图片不再代表原缓存内容。
- **BREAKING**：Convert to Plane 仅接受静态图片，拒绝 Movie 和 Sequence，移除该入口的动画帧参数传递。
- 保留失败清理、异步源图校验与撤销能力，清理转换原图复用分支和重复颜色图实现。

## Capabilities

### New Capabilities

- `material-color-images`: 所有材质创建入口的范围采样、独立颜色图、精度、配置、静态输入和资源生命周期。
- `clipboard-image-cache`: 相同剪贴板内容的有效复用、编辑后的缓存失效以及材质派生图隔离。

### Modified Capabilities

## Impact

涉及 `common/image.py`、`common/material.py`、Cutout、两个 Convert To 包、剪贴板图像获取及 Plane 创建入口和相关测试。沿用现有依赖与节点资产。

本提案取代 `reuse-conversion-source-images` 的材质原图复用策略及 Plane 动画约定；采用当前代码中的失败清理和源对象校验能力继续实施。当前主规格目录为空，新规格集中表达最终行为，后续归档时以本提案的重叠约定为准。
