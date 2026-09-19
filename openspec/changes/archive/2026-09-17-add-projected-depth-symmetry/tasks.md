## 1. 统一功能命名

- [x] 1.1 将构建模块和入口重命名为 `image_depth_symmetry.py` / `build_image_depth_symmetry_group()`，更新构建、校验与测试引用。
- [x] 1.2 将菜单、Shape 标识、节点资产名称和深度校准相关名称统一为 Depth Symmetry，清除旧名称的业务引用。

## 2. 双模式节点

- [x] 2.1 保留 Balloon 分支与参数语义，新增顺序为 `Balloon / Projected` 的 Mode；复用公共接口、清理、属性及输出坐标处理。
- [x] 2.2 直接构建 Projected 深度正面，使 Depth Direction 与 Reference Depth 控制投射，保留固定 XY 对称平面。
- [x] 2.3 复用边界平滑与正面平滑，删除含越界点的整面并清理无面支撑拓扑，处理零厚度与空结果。
- [x] 2.4 构建正面镜像与直壁补全，处理接缝合并、绕序、平滑着色和 Double Sided 正面预览。
- [x] 2.5 整理节点布局，确保直接构建、无布尔、无 Capture Attribute、无复杂几何节点组依赖。

## 3. 手势预设

- [x] 3.1 在 Cutout 对象创建阶段设置 `Lasso → Balloon`、`Polyline → Projected`，保留现有 Depth Cutout 的 Balloon / Shell 预设。
- [x] 3.2 验证两类手势的默认值、创建后 Mode 切换、深度校准输入及节点资产加载名称。

## 4. 几何与性能验证

- [x] 4.1 补充可独立运行的几何测试，覆盖非负正面、双面镜像、封闭性、顶点流形性、面绕序、直壁法线、平滑、空结果和 Depth Axis。
- [x] 4.2 将新 Balloon 分支与变更前基准比较，验证原参数行为及模式切换不污染状态。
- [x] 4.3 使用同输入、同边界平滑的普通与加密网格，分别测量 Reference Depth 和 Depth Direction 更新，记录预热后中位数及条件。
- [x] 4.4 用已确认的小车案例检查视角一致的效果对比，记录整面删除在切口处的分辨率取舍。

## 5. 资产交付

- [x] 5.1 更新资产清单和相关测试，运行 `uv run node-group build`，保存并验证 `src/anyimage/assets/O_AnyImage.blend`。
- [x] 5.2 运行相关对象创建与节点测试，检查源码、资产中的旧名称及最终差异，确认工作正常退出；不构建文档或打包扩展。
