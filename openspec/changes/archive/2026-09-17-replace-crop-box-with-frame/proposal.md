## Why

现有 Crop Box 把屏幕矩形当作 Selection，只能遮罩并紧裁图片内容，无法直接重定义 Image Empty 的完整矩形范围，也无法冻结当前视角下已经形成的透视外观。将它改为 Frame Tool，让用户以当前 Viewport 为基准重新取景，并能在同一次操作中扩大或缩小透明画布。

## What Changes

- **BREAKING**：以 Frame Tool 替换 Crop Box，统一改用 Frame 名称、Tool ID、Operator、源码边界、激活入口和文档，不保留 Crop Box 兼容入口。
- Frame 在当前 Viewport 中接受一个矩形，将该矩形定义为结果图片的完整 Canvas；矩形可小于或大于源 Image Empty 的当前投射范围。
- Frame 将所有选中的 still Image Empty 在当前视角中的投射按空间深度与 Alpha 合成为新 RGBA 图片；active Image Empty 作为结果对象和视图深度基准。
- Frame 输出尺寸以所画矩形在当前 Viewport 中的像素尺寸为依据，不超过当前 Region 分辨率，并受 Preferences 中可配置的最大长边限制。
- 结果 Image Empty 平行于当前视平面并覆盖所画矩形；所有源投射范围外保持透明。
- 结果透明边缘保留 Alpha 0，并用相邻可见颜色填充透明像素的 RGB，避免纹理插值产生黑边。
- Frame 不按可见 Alpha 紧裁结果，透明边缘属于用户定义的 Canvas。
- **BREAKING**：Frame 始终让 active Image Empty 承载合并结果，并删除其他参与合并的选中 Image Empty；不提供 Refine Selection、Invert 或 Keep Original，并删除 Crop Box 对应的三个持久 Scene Property。
- Crop Tool 组改为 Frame、Crop Lasso、Crop Polyline、Crop Perspective；其余三个 Crop 子工具的行为和独立选项保持不变。
- Frame、Crop Lasso 与 Cutout Lasso 只在拖动时进入手势；普通点击继续执行 Viewport 对象选择，但工具设置不显示 Blender fallback selection 的 Drag 选项。其他点选型 Crop 工具在首次点到另一对象时只切换选择，不开始编辑。
- 图片编辑手势只在 active object 是 Selection 内的 still Image Empty 时启动；active 未选中或不是 Image Empty 时取消并提示用户。

## Capabilities

### New Capabilities

- `frame-tool`: 规定 Frame 的工具入口、多选 Image Empty 投影合成、Viewport 分辨率基准、矩形 Canvas、透明扩展区域和结果对象放置语义。

### Modified Capabilities


## Impact

- 影响 Crop Tool 的注册、菜单激活入口、Scene Properties、Viewport 矩形交互、多源 RGBA 重采样与合成、Image Empty 删除和结果放置及相关测试。
- 主要涉及 `src/anyimage/operators/crop_tool/`、`src/anyimage/common/viewport.py`、`src/anyimage/common/image.py`、`src/anyimage/properties.py`、注册入口和 Crop Tool 内部文档。
- 不引入新的运行时依赖，不改变 Lasso、Polyline、Perspective、Server Job 或节点资产。
