## Why

现有 Depth Balloon 始终向原 Cutout 剪影收拢。用户需要另一种对称形体：轮廓随深度投射变化，两侧围绕固定 XY 平面对称，并通过直壁补成完整网格。小车独立实验已验证效果；直接构建版本在保留相同边界平滑时，比布尔原型约快 5.7–7.1 倍。

## What Changes

- 将功能命名为 **Depth Symmetry**，节点组命名为 `O Image Depth Symmetry`，提供 `Balloon / Projected` 两种模式。
- `Balloon` 保持原有行为；`Projected` 直接采样深度、调整投射方向、删除越界面、镜像并补直壁。
- Lasso 默认使用 `Balloon`，Polyline 默认使用 `Projected`；创建后仍可通过 Mode 切换。与现有 Depth Cutout 的 `Lasso → Balloon / Polyline → Shell` 对应。
- 正面保持在局部 `Z≥0`；开启 Double Sided 后，两侧关于局部 `Z=0` 对称，外边界沿 Z 轴连接，形成封闭网格。
- 复用公共采样、清理、平滑和节点接口构建函数，新模式独立构建，不使用布尔或依赖 Depth Plane、Depth Cutout 节点组。
- **BREAKING**：将节点资产名、Shape 标识 `DEPTH_BALLOON`、构建模块及相关代码名称统一为 Depth Symmetry，不保留旧名转发或兼容资产。

## Capabilities

### New Capabilities

- `image-depth-symmetry`: 双模式深度对称节点、直壁封闭、手势预设、命名和性能约束。

### Modified Capabilities

无。当前 `openspec/specs` 尚无可修改的已归档规格。

## Impact

- `tools/nodes/groups/image_depth_balloon.py`、相关公共构建函数、节点组构建与校验入口。
- `src/anyimage/operators/cutout_tool` 的 Shape 菜单、手势分派、深度校准与对象创建，以及相关界面文本。
- `src/anyimage/assets/O_AnyImage.blend` 和对应节点、对象创建、资产清单测试。
- 实现时运行相关测试与 `uv run node-group build`，更新并验证源码及资产；不新增依赖。
