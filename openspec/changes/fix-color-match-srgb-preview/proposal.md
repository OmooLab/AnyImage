## Why

Match Color 的临时预览继承目标图片的 color space，导致 `_color` 等材质图片的颜色解释影响交互判断。需要统一匹配与预览的像素约定，并保留原图片设置，使用户在自定义 OCIO 配置下也能使用一致的 sRGB 预览。

## What Changes

- Match Color 将 byte 图片当前 RGB 像素按 sRGB 解码，float 图片按 linear Rec.709 处理；目标与参考采用同一约定。
- 浮层使用独立 GPU 纹理显示 sRGB 编码后的匹配结果，显示过程与 Image color space 名称解耦。
- Rectify 与 Match Color 共用颜色转换、预览纹理和绘制入口；Rectify 在线性 Rec.709 中执行透视重采样，预览和最终输出采用同一颜色约定。
- 全分辨率结果按相同像素约定编码，保留目标原有 color space、Alpha 模式和图片编辑事务。
- 预览期间保留源图像素与绑定；确认、取消及异常退出均释放预览资源。

## Capabilities

### New Capabilities

- `color-match-srgb-preview`: 定义 Match Color 的像素解释、固定 sRGB 浮层、自定义 OCIO 下的显示与原设置保留。
- `image-edit-color-processing`: 定义 Rectify 与 Match Color 共享的颜色处理、预览与输出约定。

### Modified Capabilities

## Impact

- `src/anyimage/operators/color_reference.py` 的匹配输入、预览资源、绘制及结果编码。
- `src/anyimage/common/color_reference.py` 的参考准备与图标，以及 `common/color_space.py` 中 Match Color 使用的转换入口。
- `src/anyimage/common/image_preview.py` 的共享纹理与绘制入口，以及 `operators/rectify_tool` 的预览和最终透视采样调用。
- 对应 common 与 Operator 测试；采用 Blender 已有 GPU API 与 NumPy 转换。
