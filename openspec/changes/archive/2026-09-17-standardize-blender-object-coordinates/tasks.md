## 1. Python 建网与校准

- [x] 1.1 在生成几何的 Python 层统一 canonical frame：X=图片右、Z=图片 up、Y=图片纸内，BaseShape/Plane 未修改网格位于 `Y=0` 的 XZ 平面。
- [x] 1.2 更新 `cutout_tool/geometry.py` 的 BaseShape 顶点、UV、`world_plane_metric()`、`crop_plane_bounds()` 与 balloon profile 坐标到 XZ/Y 深度语义。
- [x] 1.3 更新 `convert_to_plane/image_plane.py` 的普通 Plane 网格与对象矩阵到 XZ 平面、front=-Y。
- [x] 1.4 更新 Depth Plane、Relief Plane 创建时的 `Depth Direction` 默认值和 `fit_image_depth_direction()`/`fit_depth_direction()` 到新坐标。
- [x] 1.5 更新 `cutout_tool/object.py` 删除 Depth Axis 相关初始化，并将 Depth Symmetry 最终朝向交给 `O Image Cutout Symmetry`。

## 2. Geometry Nodes 轴语义

- [x] 2.1 更新 `O Image Plane` 的 Grid/Cube 尺寸与 Thickness 为 X/Z 平面、Y 厚度。
- [x] 2.2 更新 `O Image Depth Plane` 的 UV、深度采样、投影和 Shell 厚度为 XZ 平面、+Y 深度。
- [x] 2.3 更新 `O Image Relief Plane` 的 Depth Direction 默认 `(0,1,0)`、基座平移和位移方向为 Y。
- [x] 2.4 更新 `O Image Cutout` 删除 `Depth Axis`，Balloon/Shell 厚度方向改为 Y。
- [x] 2.5 更新 `O Image Depth Cutout` 删除 `Depth Axis`，深度投影、Split、Shell 与 Balloon 字段改为 Y 轴语义。
- [x] 2.6 更新 `tools/nodes/common/` 中 depth surface、cutout、boundary smoothing、validity 等共享节点辅助，消除旧 Z 轴假设。

## 3. Depth Symmetry 与 Object Normal

- [x] 3.1 重写 `O Image Cutout Symmetry` 为 canonical Y 镜像，并在最后执行固定 yaw 旋转 `+Y → +X`，保持 up=Z，写入最终朝向属性。
- [x] 3.2 更新 `tools/nodes/common/normal_map.py`：移除旧 `Depth Axis`/`CUTOUT_Z_TO_X` 补偿，按 canonical frame、Y 背面反射和最终 yaw 旋转解释 Object Normal。
- [x] 3.3 更新 `O Image Layer` 与材质创建流程，使 Object Space Normal 读取新朝向属性并在渲染中匹配最终几何。
- [x] 3.4 验证 Depth Symmetry 最终 front 从 -Y 变为 -X，且 up=Z、对称轴=X 的行为可测试。

## 4. 测试与资产

- [x] 4.1 更新或新增 canonical frame、BaseShape、UV、Depth Direction、厚度方向和 Depth Axis 移除的测试。
- [x] 4.2 更新 Depth Symmetry 镜像、最终朝向和 Object Space Normal 的 front/back/wall 渲染测试。
- [x] 4.3 更新 `tools/nodes/check.py`、节点 inventory 测试和 `tests/tools/test_pack.py` 中受影响的名称与接口断言。
- [x] 4.4 运行 `uv run node-group build` 构建并校验 `O_AnyImage.blend`，检查无旧 Depth Axis、旧轴常量和 Capture Attribute。
- [x] 4.5 运行全量测试并确认正常退出，检查旧引用与最终差异；不构建文档或打包扩展。
