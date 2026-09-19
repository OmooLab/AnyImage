## 1. Selection Path 共享主链

- [x] 1.1 整理 `ImageSelectionGesture` 的完成边界，使其向实际操作提交方法传递一次内存中的 `SelectionPath`，并用 Viewport 手势测试验证各类手势与双击全选的路径值不变
- [x] 1.2 删除 Image Tool 和 Cutout 圈选 Operator 的 `selection_path_json` Property，让 Image Tool 直接消费内存 Path，并用测试验证同一 Operator 内不发生 JSON 编解码
- [x] 1.3 调整 Cutout 手势与 `open_shape_pie`，仅在创建 Shape 按钮时调用一次 `to_json()`，把同一个值设置给各 `CutoutSelectionToShape`，用交互测试验证没有令牌或额外状态
- [x] 1.4 删除 Cutout Pie Menu 前的 Selection 像素验证，用 Lasso、双击与放弃菜单测试验证 Shape 选定前不读取 RGBA、不栅格化 Mask、不扫描 Alpha

## 2. 执行阶段单次构建 Selection

- [x] 2.1 将 Image Tool 实际编辑拆为显式接收 Selection Path 的业务方法，使其成为唯一 Path-to-Mask 边界，并用本地编辑与 Refine Selection 调用次数测试验证每次操作只读取和栅格化一次
- [x] 2.2 让 `CutoutSelectionToShape.execute` 直接消费 Pie Menu 传入的 Selection Path 值并成为 Cutout 唯一的 Path-to-Mask 边界，用本地与 AI Shape 测试验证每次操作只读取和栅格化一次
- [x] 2.3 将空 Selection 的可见性检查合并到实际执行阶段的唯一栅格化结果，用测试验证点击 Shape 后正确取消且不会启动 Job 或创建对象
- [x] 2.4 修改图片编辑、Selection 输入导出与 Cutout 创建 helper，要求显式接收已读取的 RGBA 和 Selection Mask，并用像素及几何测试验证不存在内部重读或重建且结果保持等价

## 3. 清理与验证

- [x] 3.1 删除 `validate_cutout_selection`、圈选 Operator 的 JSON Property 和 helper 的隐式重读入口，使用定向 `rg` 验证 `to_json()` / `from_json()` 只剩 Cutout Pie Menu 到 Shape Operator 的跨边界用途
- [x] 3.2 增加高分辨率尺寸的调用边界回归测试，验证菜单前读取与栅格化为零、实际 Image Tool 或 Cutout 操作为一次，且不使用机器相关的耗时阈值
- [x] 3.3 更新 `docs/internals` 中 Image Tool、Cutout 与共享 Selection 流程，人工核对流程图明确“构建 SelectionPath”与“执行阶段构建 SelectionMask”的边界
- [x] 3.4 运行 Image Selection、Image Tool、Cutout 交互与几何相关测试，再运行 `uv run pytest`，确认全部测试通过
