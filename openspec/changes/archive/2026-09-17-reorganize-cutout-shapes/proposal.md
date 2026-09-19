## Why

Cutout 当前将四种形态封装在一个总节点组中，创建入口与几何算法一一绑定。已经验证的平滑 Balloon 背面适合成为深度实体的默认厚度，需要将四个创建预设与三个几何节点组分开，并明确法线生成规则。

## What Changes

- 创建入口确定为 `Flat`、`Solid`、`Depth Solid`、`Depth Balloon`，默认形态为 Solid。
- **BREAKING**：以 `O Image Cutout`、`O Image Depth Cutout`、`O Image Depth Balloon` 三个可直接用于修改器的节点组替代总 Shape 切换器与四个子组，移除旧节点名称和 Shape 菜单协议。
- Flat 与 Solid 共用 `O Image Cutout`，分别以 Thickness 0 和 1 创建；普通与深度 Cutout 均提供 Balloon / Uniform 两种厚度方式，默认 Balloon。
- Depth Solid 使用经过五张图验证的新背面算法，保留正面深度位置，背面按平滑中心位置与 o_balloon 构造；Uniform 保留等厚 Depth Surface 行为。
- Depth Balloon 保留原塑形算法，默认开启 Double Sided。
- 三个节点组各自提供适用的 Cleanup、Smooth 和轴向输出；深度 Cutout 保持 Cleanup 在 Split 前、Split 使用原始深度差的修正。
- Normal Map 勾选仅控制 Flat 与 Solid；Depth Solid 与 Depth Balloon 始终生成并使用各自所需的法线图。

## Capabilities

### New Capabilities

- `cutout-shape-presets`: 四个入口、三个节点组、创建默认值与两种厚度方式。
- `depth-cutout-volume`: 深度表面上的平滑 Balloon 背面、等厚模式、清理分离及闭合行为。
- `cutout-normal-policy`: 按入口选择法线生成策略，保持 AI 可用性约束及材质连接正确。

### Modified Capabilities

无。当前 `openspec/specs/` 尚无已归档规范；本提案记录完整目标要求，并在设计中说明与现有未归档变更的关系。

## Impact

- `src/anyimage/operators/cutout_tool/` 的形态标识、菜单、节点加载、默认参数、法线策略和材质绑定，以及 Cutout 工具属性。
- `tools/node_assets/` 的构建、布局与验证；`src/anyimage/assets/O_AnyImage.blend` 中的 Cutout 资产。
- Cutout 交互、Job 参数、网格求值和节点资产测试，以及节点资产说明。
- 原型位于 `build/cutout_surface_balloon/`，实施时将必要算法纳入正式源码。无需新增依赖。
