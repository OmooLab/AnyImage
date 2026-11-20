# image-edit-color-processing Specification

## Purpose
规定透视校正与色彩匹配共用的像素解释，明确 byte 和 float 图片的解码、线性处理和结果编码，使交互预览与最终图片采用相同的颜色和透明度约定。

## Requirements

### Requirement: Rectify and Match Color share color processing boundaries

Rectify 与 Match Color SHALL 共用 `common` 的颜色转换函数。两种工具 SHALL 将 byte 业务 RGB 按 sRGB 解码，将 float 业务 RGB 按 linear Rec.709 使用，在线性 Rec.709 中执行各自颜色处理或重采样；byte 结果 SHALL 编码为 sRGB，float 结果 SHALL 保留线性值。颜色转换 SHALL 保留 Alpha。

#### Scenario: Both tools consume the same business pixels
- **WHEN** Rectify 与 Match Color 读取相同存储类型和业务 RGBA 的图片
- **THEN** 两者使用相同的线性颜色解释，解释与 Image color space 名称无关

#### Scenario: Rectify interpolates contrasting colors
- **WHEN** Rectify 对黑白或其他高反差颜色执行透视重采样
- **THEN** RGB 在线性 Rec.709 中插值，继续使用已有预乘 Alpha 采样与 straight Alpha 输出语义

### Requirement: Rectify displays a fixed sRGB overlay

Rectify SHALL 将线性 RGBA 转为 sRGB 显示纹理，在浮层中保持像素方向和透明混合，并支持缺少 `sRGB` 条目的 OCIO 配置。

#### Scenario: Rectify previews a float image
- **WHEN** 用户调整 float 图片的 Rectify 宽高比
- **THEN** 预览将线性 RGB 编码为 sRGB 显示，最终 float 结果保持线性 RGB 和原 color space、Alpha 模式

#### Scenario: Rectify runs with a custom OCIO configuration
- **WHEN** OCIO 配置没有名为 `sRGB` 的色彩空间
- **THEN** Rectify 使用同一显示转换绘制浮层

### Requirement: Rectify preview and output use the same color interpretation

Rectify SHALL 为代理预览和最终透视重采样使用同一线性颜色约定，保留现有输出尺寸限制、可见 Alpha trim、placement、原图片 color space、Alpha 模式与共享用户隔离。取消、返回选点及失败 SHALL 释放该阶段纹理并保留原图状态。

#### Scenario: Rectify is confirmed
- **WHEN** 用户调整宽高比后确认有效 Rectify 操作
- **THEN** 最终结果使用与预览一致的颜色处理和存储类型编码，尺寸和放置按既有规则计算

#### Scenario: Rectify returns to point selection
- **WHEN** 用户在宽高比阶段按 Backspace 返回选点
- **THEN** 当前预览纹理引用被释放，源图像素、设置和绑定保持不变
