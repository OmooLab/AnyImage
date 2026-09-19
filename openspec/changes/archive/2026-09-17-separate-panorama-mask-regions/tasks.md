## 1. 分面

- [x] 1.1 `build_image_depth_panorama_group` 用 `GeometryNodeSeparateGeometry`（domain FACE，selection 为面心 `invalid`）替换 `validity.delete_invalid_faces`，取出 `Selection` 低 mask 区域与 `Invert` 高 mask 区域
- [x] 1.2 去掉 Panorama 对 `validity` 的导入，确认 `O Image Depth Plane` 仍调用该函数

## 2. 两条分支

- [x] 2.1 高 mask 分支保持原链路：`split_depth_surface` → `build_surface_camera` → `smooth_boundary_depth` → 半径表达式 → Set Position → `remove_attribute_pattern` → `smooth_cut_boundary`
- [x] 2.2 去掉按点回退的 `fallback` Switch，无效判定只保留 Separate Geometry 那一处比较
- [x] 2.3 低 mask 分支加独立 Set Position，位置为单位方向乘 `Dome Radius`；不接 Depth Split、深度模糊与切口带平滑
- [x] 2.4 `Join Geometry` 合并两条分支，Depth Mask Switch 关闭时取合并结果、打开时取高 mask 分支
- [x] 2.5 Flip Faces、Shade Smooth 与 `inherit_material_slots` 保持在合并之后，两条分支共用同一套输出处理
- [x] 2.6 核对 `Depth Mask`、`Dome Radius`、`Mask Threshold` 的 description 与新语义一致

## 3. 测试

- [x] 3.1 `test_mask_threshold_culls_faces` 改为分面语义：打开时只输出高 mask 区域，关闭时输出完整球面且低 mask 区域落在 `Dome Radius`
- [x] 3.2 重写 `test_masked_area_falls_back_to_the_dome_radius`：关闭时按区域断言半径、`Dome Radius` 改变后的两个落点、`Depth Scale` 为 0 的整球结果
- [x] 3.3 补断言：关闭时低 mask 区域写入与有效侧相差一个数量级的深度，其半径仍为 `Dome Radius`
- [x] 3.4 补断言：关闭时接缝两侧各自持有顶点，接缝在两侧都是自由边，顶点数多于不分面时的输出
- [x] 3.5 补断言：关闭且 Boundary Smooth 大于 0 时低 mask 区域仍落在 `Dome Radius` 球面
- [x] 3.6 确认 `test_alpha_cut_keeps_the_ring_sharing_the_face_centre_contour`、`test_invalid_depth_does_not_bleed_into_alpha_boundary`、`test_panorama_validity_cut_smoothing_stays_in_two_ring_band` 在分面后仍通过
- [x] 3.7 运行 `uv run pytest`，确认全景与共享切口规则的既有测试全部通过

## 4. 资产与收尾

- [x] 4.1 运行 `uv run node-group build`，确认节点资产构建与校验通过、Capture Attribute 为零
- [x] 4.2 检查源码、测试与资产中不再有 Panorama 走 Delete Geometry 的旧路径，确认最终差异只涉及本次范围
- [x] 4.3 简要报告调整内容与验证结果

## 5. 追加调整

- [x] 5.1 低 mask 分支在合并前接入 `smooth_cut_boundary`，由 Boundary Smooth 控制，不传 Depth Split 边界
- [x] 5.2 Depth Scale 为 0 且 Depth Mask 关闭时旁路分面与后续处理，直接输出 `Dome Radius` 的完整球面；Depth Mask 打开时仍按 mask 排除
- [x] 5.3 `test_boundary_smooth_relaxes_both_masked_region_boundaries`：两个区域的接缝带都移动、内部不动，低 mask 区域内部仍在 `Dome Radius`
- [x] 5.4 `test_flat_scale_without_mask_returns_a_whole_sphere`：面数与顶点数同完整球面一致、无自由边、半径等于 `Dome Radius`
- [x] 5.5 重跑 `uv run node-group build` 与 `uv run pytest`，确认资产与测试通过
