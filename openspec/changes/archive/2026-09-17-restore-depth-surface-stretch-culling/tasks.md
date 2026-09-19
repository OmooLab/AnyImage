## 1. 锁定节点接口与求值行为

- [x] 1.1 扩展 Cutout 节点资产结构测试，规定 `Stretch Limit` 仅连接 `O Image Depth Surface`、位于 Options、Factor 范围为 `0–1` 且默认值为 `0`，并运行对应 `tests/test_cutout_objects.py` 用例
- [x] 1.2 增加真实 Blender 求值测试，覆盖 Stretch Limit 为 `0` 时保留完整表面、正阈值分别保留阈值内 Edge 与删除超限 Edge，并验证调整 Depth Scale 会实时改变拉伸判断
- [x] 1.3 增加剔面后拓扑测试，验证 `Face Count == 0` 的 Edge 与 Point 被删除，而仍属于一个 Face 的开放边界保留

## 2. 构建 Depth Surface 拉伸剔面

- [x] 2.1 在 `O Image Depth Surface` 的 Set Position 前以 Point Domain 捕获 Edge Vertices Distance 原值，并在 Set Position 后以同一个 Field 直接求当前值
- [x] 2.2 比较 `原始距离 / 当前距离 < Stretch Limit`，以 `POINT / ALL` 删除超限位置及相邻拓扑；默认 `0` 自然关闭剔面
- [x] 2.3 在 Stretch Culling 后按 Edge Neighbors Face Count 删除纯线 Edge，再按 Vertex Neighbors Face Count 删除无 Face Point，并将清理后的几何交给 Thickness 与 Smooth
- [x] 2.4 在外层 `O Image Cutout` 暴露并只向 Depth Surface 分支连接 `Stretch Limit`，保持其他 Shape、现有 Mesh Island Cleanup 和 Depth 数据输入不变

## 3. 节点资产、文档与验证

- [x] 3.1 更新 `tools/node_assets/validate_cutout.py`，构建并验证 `src/anyimage/assets/O_AnyImage.blend` 的接口、节点顺序、无重叠与几何求值
- [x] 3.2 更新 Cutout 用户说明、`docs/internals/operators/cutout-tool.md` 与 `docs/internals/node-assets.md`，说明 Stretch Limit 的零值关闭、剩余比例语义和松散拓扑清理
- [x] 3.3 运行 Cutout 定向测试、`uv run build_node` 与 `uv run pytest`，确认 Vector Depth RGB/Validity Alpha、其他三个 Shape 和现有 Cleanup 没有回归

## 4. 按最终节点接法修正

- [x] 4.1 移除 Projected Position Capture 与 Sample Index，以同一个 Edge Vertices Distance Field 分别捕获原值并在完整 XYZ Set Position 后直接求当前值
- [x] 4.2 将拉伸 Delete Geometry 改为 Point Domain，并保留后续纯线 Edge 与孤立 Point 清理
- [x] 4.3 同步结构与真实求值测试、节点资产和文档，运行 OpenSpec、节点构建及全量测试
