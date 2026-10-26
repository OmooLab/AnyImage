## Why

inverse 视图颜色可能超出普通 sRGB 贴图的范围。鳄鱼对比确认，固定上限 T＝4、各通道分别截断，再应用 Gamma 0.75，能在普通颜色贴图中取得可接受的亮度和对比，并使同一颜色的处理结果保持一致。

## What Changes

- **BREAKING**：关闭 Compensate Image Colors 且普通 byte 图匹配可用 inverse 空间时，将 inverse 解码得到的线性 RGB 各自截断到 0～4，除以 4，应用 Gamma 0.75，再编码为 sRGB。
- 直接写回已准备的材质 `_color` 或笔刷目标 Image 并打包，保留身份、尺寸、Alpha 和绑定。所有像素使用同一固定变换。
- 记录已归一化状态，支持重复配置、编辑、颜色图准备和保存重载；全新原始内容替换时清除状态。
- 开启补偿时沿用 inverse 解释，默认保持开启；直接 sRGB 和 float/HDR 输入沿用现有处理。

## Capabilities

### New Capabilities

- `image-color-normalization`：固定 T＝4、各通道截断、Gamma 0.75、sRGB 编码及原地更新生命周期。

### Modified Capabilities

- `material-view-adaptation`：补偿开关、材质与笔刷共用颜色配置入口。
- `material-color-images`：材质 `_color` 图的处理和打包持久化规则。
- `clipboard-image-cache`：笔刷原地改值后的缓存有效性与重复粘贴行为。

## Impact

- 实现集中在 `common/material.py`、`common/color_space.py`、`common/color_image.py`，图像事务复用 `common/image.py`。
- 笔刷交付复用相同策略，偏好提示与翻译说明固定参数。
- 验证 Blender inverse 求值、数值映射、Alpha、持久化、材质入口、笔刷缓存及失败恢复。
