## 1. 共享相机采样

- [x] 1.1 在 `build_surface_camera` 内部求值 `edge_boundary_field` 得到切口边界，删除 `always_vertex` 参数，让切口点与 Depth Split 切边走同一条深度替换路径
- [x] 1.2 为 `build_surface_camera` 增加可选排除字段并施加在切口边界上：被排除的点保持自身采样
- [x] 1.3 更新 `build_surface_camera` 的 docstring，说明切口取相邻面深、射线方向不变、排除字段的语义

## 2. 三个组接入

- [x] 2.1 `O Image Depth Plane`：去掉 `always_vertex` 用法，外框与切口同规则，不再传排除字段
- [x] 2.2 `O Image Depth Panorama`：去掉 `always_vertex` 用法，不传排除字段
- [x] 2.3 `O Image Depth Cutout`：去掉局部 `outline` 变量与 `always_vertex` 传参，确认轮廓与切边仍由内建规则覆盖
- [x] 2.4 确认 `O Image Relief Plane`、Cutout 创建入口与材质接线未受影响
- [x] 2.5 `delete_invalid_points` 改为 `delete_invalid_faces`：Delete Geometry 用 FACE 域，去掉残留边的第二次删除
- [x] 2.6 `O Image Depth Plane`：取消外框例外，`build_surface_camera` 去掉排除字段，全部自由边界点取相邻面采样

## 3. 测试

- [x] 3.1 Plane：在无效侧写入与有效侧相差一个数量级的深度，断言 mask 切口点跟随相邻面深、不出现尖刺（`test_plane_validity_hole_blurs_depth_and_protects_rectangle`）
- [x] 3.2 Panorama：在无效侧写入差异距离，断言切口圈径向距离跟随相邻有效面（`test_panorama_blurs_opening_radially_and_keeps_invalid_distance`）
- [x] 3.3 断言切口点保持自身射线方向（Plane 相机横纵坐标不变、Panorama 经纬方向不变）
- [x] 3.4 把 `test_valid_only_deletes_invalid_points_and_wire_edges` 的保留点断言改为「面中心采样低于 Mask Threshold 才删面」（改名 `test_valid_only_keeps_faces_covering_valid_samples`），保留 Depth Mask 关闭时逐位不变的对比
- [x] 3.5 断言 Plane 原画幅外框取相邻面深（`test_outline_points_use_adjacent_face_depth_without_split`），以及不存在相邻保留面的自由点输出坐标有限（`test_validity.py`）
- [x] 3.6 运行 `uv run pytest`（至少覆盖 `tests/tools/nodes/test_depth_relief_planes.py`、`test_boundary_depth.py`、`test_depth_surface_split.py`、`test_image_depth_panorama.py`）

## 4. 资产与收尾

- [x] 4.1 运行 `uv run node-group build`，确认节点资产构建与校验通过、Capture Attribute 为零
- [x] 4.2 检查源码与测试中不再有 `always_vertex` 及旧路径引用，确认最终差异只涉及本次范围
- [x] 4.3 `O Image Depth Panorama` 的无效判定改在面心求值并去掉 `Invalid Distance`，Depth Mask 关闭时保留的无效面整片落到 `Dome Radius`（同时是 Depth Scale 0 的球半径），并补面心轮廓、切口点半径与 dome 回退断言
