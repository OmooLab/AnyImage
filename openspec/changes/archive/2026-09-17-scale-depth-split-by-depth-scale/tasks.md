## 1. Split 判据

- [x] 1.1 `split_depth_surface` 增加 Depth Scale 参数，落差项乘该因子，并按新含义更新 docstring。
- [x] 1.2 `O Image Depth Plane`、`O Image Depth Cutout`、`O Image Depth Panorama` 传入各自的 Depth Scale，并把 Depth Split 的参数说明改为随 Depth Scale 缩放。

## 2. 测试

- [x] 2.1 反转 `test_split_topology_uses_depth_before_display_scaling`：Depth Scale 为 0 时不切开且拓扑与关闭 Split 相同，为 1 时与现有结果一致。
- [x] 2.2 更新 `test_split_mapping_and_uniform_scale` 中 Depth Scale 为 0 仍保持切边的断言。
- [x] 2.3 为 `O Image Depth Cutout` 与 `O Image Depth Panorama` 补充 Depth Scale 为 0 不切开的覆盖。

## 3. 资产与规范

- [x] 3.1 运行 `uv run node-group build` 重建并验证 `O_AnyImage.blend`。
- [x] 3.2 修订 `reorganize-cutout-shapes` 中 `depth-cutout-volume` 的 Split 条目，使其与投影后落差判据一致。
- [x] 3.3 运行相关节点测试并确认通过。
