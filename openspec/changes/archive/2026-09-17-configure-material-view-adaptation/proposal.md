## Why

用户实测材质颜色贴图在 inverse 类颜色空间下使用 STRAIGHT 边缘更好，在 sRGB 下使用 PREMUL 效果合适。当前材质入口自动适配场景 View Transform 并统一设置 PREMUL，需要提供着色偏好，让用户选择适配方式并配套正确的 Alpha 模式。

## What Changes

- Preferences 新增 Shading 分组和 Adapt to Scene View Transform（适配场景视图变换）开关，默认关闭。
- 开启时根据当前场景选择对应 inverse 颜色空间，并设置 STRAIGHT。
- 关闭时使用 sRGB + PREMUL；开启适配但实际回退到 sRGB 时也使用 PREMUL。
- Preferences 是适配开关的唯一控制来源；新建材质读取当前设置，已创建的材质贴图保留原配置。
- Plane、Depth Plane、Cutout 和剪贴板 Mesh 材质的 Color Image 统一应用该策略，保留业务像素和源图片独立性。

## Capabilities

### New Capabilities

- `material-view-adaptation`: 材质视图适配偏好、颜色空间与 Alpha 配对、应用时机和像素保留。

### Modified Capabilities

无。当前主规格目录为空；与活动变更 `enable-image-alpha-blending-and-premul` 的 Mesh Color 默认值重叠部分，在实施和归档时按本变更的配对策略协调。

## Impact

- `src/anyimage/preferences.py`：偏好属性、统一读取入口和 Shading UI。
- `src/anyimage/common/material.py`：颜色空间选择与材质 Color 配置。
- `src/anyimage/common/image.py`：复用现有业务像素读取能力；材质专属策略由 `common/material.py` 承担。
- `src/anyimage/operators/clipboard_image/actions.py`：接入公共材质 Color 配置。
- Blender 偏好注册、材质配置、Alpha 数据保留和转换入口测试。
