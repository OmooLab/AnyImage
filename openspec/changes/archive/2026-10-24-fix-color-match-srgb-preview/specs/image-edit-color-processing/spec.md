## ADDED Requirements

### Requirement: Rectify and Match Color share color processing boundaries

Rectify 与 Match Color SHALL 共用 `common` 的颜色转换及浮层纹理绘制入口。两种工具 SHALL 将 byte 业务 RGB 按 sRGB 解码，将 float 业务 RGB 按 linear Rec.709 使用，在线性 Rec.709 中执行各自颜色处理或重采样；byte 结果 SHALL 编码为 sRGB，float 结果 SHALL 保留线性值。颜色转换 SHALL 保留 Alpha。

#### Scenario: Both tools consume the same business pixels
- **WHEN** Rectify 与 Match Color 读取相同存储类型和业务 RGBA 的图片
- **THEN** 两者使用相同的线性颜色解释，解释与 Image color space 名称无关

#### Scenario: Rectify interpolates contrasting colors
- **WHEN** Rectify 对黑白或其他高反差颜色执行透视重采样
- **THEN** RGB 在线性 Rec.709 中插值，继续使用已有预乘 Alpha 采样与 straight Alpha 输出语义

### Requirement: Both overlays share fixed sRGB presentation

Rectify 与 Match Color SHALL 共用从线性 RGBA 到 sRGB 显示纹理的准备与绘制逻辑，统一像素方向、显示裁剪和 Alpha 混合。该入口 SHALL 使用普通 GPU 纹理，并 SHALL 在 OCIO 缺少 `sRGB` 条目时正常工作。各工具 SHALL 保留自身布局尺寸、宽高比、HUD、交互及刷新策略。

#### Scenario: Rectify previews a float image
- **WHEN** 用户调整 float 图片的 Rectify 宽高比
- **THEN** 预览将线性 RGB 编码为 sRGB 显示，最终 float 结果保持线性 RGB 和原 color space、Alpha 模式

#### Scenario: Both overlays run with a custom OCIO configuration
- **WHEN** OCIO 配置没有名为 `sRGB` 的色彩空间，用户分别启动两种工具
- **THEN** 两者正常显示预览，使用相同的显示转换与透明混合规则

### Requirement: Rectify preview and output use the same color interpretation

Rectify SHALL 为代理预览和最终透视重采样使用同一线性颜色约定，保留现有输出尺寸限制、可见 Alpha trim、placement、原图片 color space、Alpha 模式与共享用户隔离。取消、返回选点及失败 SHALL 释放该阶段纹理并保留原图状态。

#### Scenario: Rectify is confirmed
- **WHEN** 用户调整宽高比后确认有效 Rectify 操作
- **THEN** 最终结果使用与预览一致的颜色处理和存储类型编码，尺寸和放置按既有规则计算

#### Scenario: Rectify returns to point selection
- **WHEN** 用户在宽高比阶段按 Backspace 返回选点
- **THEN** 当前预览纹理引用被释放，源图像素、设置和绑定保持不变
