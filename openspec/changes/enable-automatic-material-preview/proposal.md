## Why

用户完成 Cutout 后，如果发起操作的 3D 视图仍处于 Solid 或 Wireframe，就看不到新物体的材质颜色。Convert to World 和 Convert to Panorama 还需要让该视图使用场景 World，才能看到刚生成的环境。

## What Changes

- 完整版和 Lite 的偏好设置新增「自动材质预览」，默认开启。关闭后，三个操作均保留用户的视图设置。
- Cutout 准备创建物体时，仅将发起操作的 3D 视图从 Solid 或 Wireframe 切换到 Material Preview。已有的 Material Preview 或 Rendered 模式保持原样。
- Convert to World 和 Convert to Panorama 成功应用结果后，执行相同的模式判断，并勾选最终模式下的 Lighting → Scene World。其余视图参数保持原值。

## Capabilities

### New Capabilities

- `automatic-material-preview` 规定相关操作的预览时机、目标视图、模式切换与 Scene World 行为。

### Modified Capabilities

## Impact

涉及共用偏好设置、界面翻译、视图辅助函数以及三个操作的结果应用入口。Lite 的适用操作为本地 Cutout 和 Convert to World。
