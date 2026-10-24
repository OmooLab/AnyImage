## Why

颜色参考目前只能从图片右键菜单设置，当前参考不可见，且 `Set Color Reference` 与实际高频的匹配操作并列，增加了菜单负担。将参考状态与选择统一放到侧边栏，可以用一个控件完成查看、选择和清空，同时避免把生成的辅助贴图误选为颜色参考。

## What Changes

- 在 3D View 的 AnyImage 侧边栏新增独立的 `Color Match` Panel。
- Panel 使用一个图片选择框同时呈现和选择当前 Scene 的 Color Reference，默认允许为空，并可直接替换或清空。
- Panel 在选择框下显示由当前参考可见像素提取的五色色板，作为参考统计的即时说明。
- Color Reference 候选仅包含有效静态 Image，不显示名称属于 `_normal`、`_depth`、`_color` 输出类别的图片。
- 从 Image Empty、AnyImage Mesh 和材质 Image Texture 的 `AnyImage` 右键菜单移除 `Set Color Reference`，保留 `Match Color Reference`。
- 移除不再使用的 `Set Color Reference` Operator，不保留旧入口或兼容层。

## Capabilities

### New Capabilities

- `color-match-panel`: 定义侧边栏颜色参考的呈现、选择、清空、候选过滤和 Scene 状态行为。

### Modified Capabilities

- `object-image-actions`: AnyImage Mesh 右键菜单不再提供设置颜色参考，只保留对当前 Color Image 执行匹配。
- `texture-node-image-actions`: 材质 Image Texture 右键菜单不再提供设置颜色参考，只保留对当前节点图片执行匹配。

## Impact

- Blender 侧 `AnyImageSettings` 的 Color Reference 属性、3D View 侧边栏 Panel、类型注册和图片菜单。
- 颜色参考 Operator 与相关菜单、对象目标、节点目标及注册测试。
- 不改变目标解析、结果提交、Undo 或 AI/Job Server 边界。
