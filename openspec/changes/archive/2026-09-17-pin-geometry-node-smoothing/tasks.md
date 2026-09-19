## 1. 共享实现

- [x] 1.1 在 `tools/nodes/common/smoothing.py` 实现 pinned 平滑构建函数：Repeat 每轮生成内部 Blur 目标、边界条带 0.5 权重目标与 `|Blur(Normal, 10)|` 锐度系数，按 `weight × region` 混向目标，并支持可移动分量掩码
- [x] 1.2 删除 `expand_smooth()`，保留 `edge_boundary_field()` 供作用范围与边界分支使用
- [x] 1.3 更新 `tools/nodes/common/boundary_smoothing.py`，轮廓与切边权重留在作用范围层，顶点平滑改走共享函数

## 2. 节点组

- [x] 2.1 确认三个深度节点组的顶点平滑经 `smooth_cut_boundary()` 走共享函数，调用签名不变
- [x] 2.2 删除 `image_cutout_symmetry.py` 的 `_apply_planar_relax()` 与旧的平面内偏移路径，Fill 与 Seam 改走共享函数并传对称平面内的可移动分量
- [x] 2.3 确认公开接口没有新增 pin 输入，法线平滑、深度模糊、掩码与统计模糊保持不变

## 3. 测试

- [x] 3.1 在 `tests/tools/nodes/test_boundary_smoothing.py` 覆盖边界条带松弛、尖锐处位移更小与可移动分量掩码，保留范围外不动、迭代 0 关闭、轮廓与切边权重差异的既有覆盖
- [x] 3.2 确认 Fill 与 Seam 改走共享函数后镜像焊接与闭合性测试通过；`test_cutout_symmetry.py` 中 4 个失败属于 `refine-cutout-symmetry-seam` 未完成项，改动前后一致
- [x] 3.3 运行节点与 operator 测试：919 passed（含 60 subtests），仅上述 4 个既有失败

## 4. 资产

- [x] 4.1 运行 `uv run node-group build` 更新并验证 `src/anyimage/assets/O_AnyImage.blend`
- [x] 4.2 检查几何节点与嵌套组 Capture Attribute 为零，确认源码、资产与测试无残留旧平滑路径

## 5. Fill Smooth 语义调整

- [x] 5.1 让共享平滑支持普通形态：不接边界条带分支时只使用邻域平均目标与 region 权重，pin 形态与普通形态共用同一个迭代循环
- [x] 5.2 `Fill Smooth` 改走衔接带形态，falloff 由两圈扩大到 `FILL_SMOOTH_RINGS = 4` 圈，Seam 保持 pin
- [x] 5.3 覆盖普通平滑的邻域平均目标与衔接带第三圈仍受力、配置圈数之外保持原位
- [x] 5.4 重建节点资产并运行相关测试

## 6. 衔接带锚点与 pin 拆分

- [x] 6.1 把共享平滑的 pin 拆成 `pin_boundary` 与 `pin_sharp` 两个独立开关，深度三组与 Seam 保持两者开启
- [x] 6.2 `Fill Smooth` 保留 `Pin Sharp`、关闭 `Pin Boundary`，锚点由界外轮廓改为 front 的完整边界带，对称轴上的点因此纳入作用范围
- [x] 6.3 更新测试：衔接带使用邻域平均但保留锐度权重、对称轴上的点产生位移，并修正 `refine-cutout-symmetry-seam` 里与旧 Fill 语义冲突的断言
- [x] 6.4 重建节点资产并运行相关测试
