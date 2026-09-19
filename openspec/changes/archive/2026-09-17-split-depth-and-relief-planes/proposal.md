## Why

整图相机投影与固定底面浮雕需要独立的转换入口和几何节点。相机投影生成背景模型时，透明区域需要参与几何剔除，同时保留修改器中调整网格密度的能力。

## What Changes

- **BREAKING**：拆分现有 Relief / Camera 模式，`Convert to Depth Plane` 专门生成相机投影曲面，新增 `Convert to Relief Plane` 生成固定底面浮雕。
- 两个入口分别加载 `O Image Depth Plane` 和 `O Image Relief Plane`，各自提供所需参数，移除 Mode 选择与跨模式参数。
- Depth Plane 在基础网格细分后、深度投影与厚度处理前，根据depth.exr 有效性 Alpha 宽松剔除几何。修改器提供默认开启的 `Valid Only` 开关，保留 `Subdivide` 动态调节。
- 宽松剔除使用深度有效性 Alpha < 1，经 Boolean / Point 的 Evaluate on Domain 后连接 Face / All 的 Delete Geometry。
- Depth Plane 生成并使用 Object Space Normal Map；Relief Plane 延续 Tangent Space Normal Map。

- Depth Plane 复用 Depth Cutout 的 Smooth 模块，在最终曲面或厚度几何上执行平滑，提供 Smooth 和 Smooth Weight。

## Capabilities

### New Capabilities

- `separate-depth-relief-planes`：独立转换入口、节点资产、参数及对应法线空间。
- `depth-plane-alpha-culling`：可开关、随细分重新求值的 Alpha 几何剔除。

### Modified Capabilities

无；当前 `openspec/specs/` 无已归档规范。本提案接续 `unify-depth-plane-and-artifact` 的现有实现。

## Impact

涉及转换 Operator、菜单与注册、Server Job 参数与法线产物、对象和材质创建、节点资产构建脚本、布局、验证及测试。节点资产文档随接口更新。复用现有深度协议与 Object Normal 生成能力，无需新增依赖。实施时保留工作区已有修改；执行测试，节点资产构建与 Blender 视觉验收单独安排。
