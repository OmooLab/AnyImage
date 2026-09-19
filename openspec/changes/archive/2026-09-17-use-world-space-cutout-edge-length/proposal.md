## Why

Cutout 的 Mesh Detail 使用源图像像素间距，用户难以从 Image Empty 的外观预判生成密度。改用场景物理长度，让网格密度由明确的目标边长控制，并通过裁切区域的相对尺寸限制生成成本。

## What Changes

- **BREAKING**：将 Mesh Detail 枚举替换为带长度单位的 Edge Length 浮点参数，初始默认值为 0.1 m。
- 按世界变换和场景 Unit Scale 计算采样间距，图片分辨率与画布大小不参与密度定义。
- Preferences 使用 Minimum Relative Edge Length 百分比替换 Maximum Cutout Mesh Resolution，默认 1%；实际间距取用户长度与裁切包围盒世界长边乘比例的较大值。
- 普通轮廓与 Fine Outline 共用有效间距语义；相对限制作用于目标采样间距，轮廓适配允许更短的边。
- 限制生效时展示实际采用的目标长度。

## Capabilities

### New Capabilities

- `cutout-edge-length`: Cutout 的物理目标边长、相对密度限制及一致的采样与界面行为。

### Modified Capabilities

无。当前 openspec/specs 下无已归档能力规范。

## Impact

涉及 properties.py、preferences.py、cutout_tool 的交互、Operator、几何与 Fine Outline 采样链，以及相关注册、偏好与几何测试。移除旧枚举映射、像素间距协议和旧密度上限入口；无需新增依赖。
