## Why

Depth Surface 将基础 Cutout 网格投影到相机空间 XYZ 后，深度断层会把相邻顶点拉成跨越前后景的长面。当前 Cleanup 只在 Shape 变形前删除小型 Mesh Island，无法识别这些仍连接在主体上的拉伸面，也无法清理剔面后留下的单线拓扑。

## What Changes

- 为 Depth Surface 增加 **Stretch Limit**，根据深度投影前后的边长比例剔除过度拉伸的 Edge 及其关联 Face。
- **Stretch Limit** 默认值为 `0`，表示关闭拉伸剔面；正值越大，清理越严格。
- 在 Depth Surface 投影前按 Point Domain 捕获原始边长，投影 Set Position 后直接重新计算边长，使判据跟随实际 `Depth Scale` 结果且不依赖 Depth EXR 的额外通道。
- 以 Point Domain 删除超限位置及其相邻拓扑，再删除 `Face Count == 0` 的松散 Edge 和 Point，最后执行 Depth Surface 后续 Thickness 与 Smooth；现有 Mesh Island Cleanup 语义保持不变。
- 更新 Cutout 节点资产、验证、Blender 求值测试及用户与内部文档。

## Capabilities

### New Capabilities

- `depth-surface-stretch-culling`: 规定 Depth Surface 的边长比例判据、关闭语义、松散拓扑清理及节点处理顺序。

### Modified Capabilities

无。

## Impact

- 影响 `tools/node_assets/build_cutout.py` 中 `O Image Depth Surface` 与外层 `O Image Cutout` 的接口和节点主链。
- 影响 `src/anyimage/assets/O_AnyImage.blend`、节点资产验证及 `tests/test_cutout_objects.py` 的真实 Blender 求值覆盖。
- 需要同步 Cutout 用户说明、内部 Operator 文档与节点资产文档。
- 不修改 Server Job、模型推理、Depth Metadata 或 Vector Depth EXR 的 RGB/Validity Alpha 协议，不新增依赖。
