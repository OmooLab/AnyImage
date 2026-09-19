## 1. 共用投影采样

- [x] 1.1 将 Homography 求解、预乘 Alpha 双线性重采样和输出资源限制整理为 Frame 与 Crop Perspective 可复用的公共 Image 像素函数，删除具体工具之间的反向依赖，并用数值、透明边缘、范围外采样、退化矩阵和上限测试验证
- [x] 1.2 让 Crop Perspective 改用公共投影采样函数，移除原模块中的重复实现，并运行既有 Perspective 输出、预览、Alpha、placement 和异常测试确认行为不变

## 2. Frame 像素与空间计算

- [x] 2.1 实现每个选中 Image Empty 的世界四角到 Region 投影、Frame 与 active 投射 Quad 相交验证，以及 Frame 像素中心到各源图片像素的映射；用透视、正交、范围内、部分越界、无 active 相交和近退化视角测试验证
- [x] 2.2 实现基于 Frame 屏幕像素、Region 尺寸与 Preferences 最大长边的输出尺寸计算，保留完整透明 Canvas 且不执行 Alpha 紧裁；用其他源分辨率变化、较小 Frame、较大 Frame、透明源边缘、整数宽高比和输出上限测试验证
- [x] 2.3 实现多源分块采样、逐像素几何深度排序和预乘 Alpha source-over 合成，active 在相同深度置顶；用前后遮挡、透明叠加、倾斜平面交叉、共面 active 和 Frame 外样本测试验证
- [x] 2.4 实现穿过 active 对象世界原点的视平面反投影与结果 Image Empty 矩阵/显示范围计算，确保本地 XY 平行视平面、正面朝向观察者、屏幕四边对应 Frame；用透视、正交、平移 active 对象和非均匀源变换测试验证

## 3. Frame Tool

- [x] 3.1 新增 `crop_tool/frame.py`，实现以 active still Image Empty 为基准、收集所有选中 still Image Empty、忽略非图片对象且可从 Region 任意位置开始的矩形 modal、Overlay、状态文本、取消和错误清理；用单选、多选、无效 active、选中视频、混合对象、微小矩形、工具切换和取消测试验证
- [x] 3.2 在 Frame 完成时冻结视图和所有参与对象状态，创建 packed 合成 Image，并以事务式更新让 active Object 承载新的 Image、世界矩阵、居中 offset 和显示尺寸，再删除其他参与 Image Empty；用对象 identity、名称、colorspace、Collection、共享 Image 生命周期、被忽略对象、异常回滚和单步 Undo 测试验证
- [x] 3.3 验证多张倾斜源图片在 Frame 前后的操作视角投射与 Alpha 层叠一致，并验证改变视角后结果保持已烘焙合成图而不再跟随原投射平面

## 4. 替换 Crop Box

- [x] 4.1 将 Crop Tool 组、注册导出和默认激活入口改为 Frame、Crop Lasso、Crop Polyline、Crop Perspective，统一使用 `FrameTool`、`anyimage.frame` 和 Frame Operator ID，并用注册顺序、ToolDef、菜单与激活测试验证
- [x] 4.2 从 Crop Selection Operator 删除 BOX 的 Refine Selection、Invert 和 Keep Original 映射，删除 Crop Box 专用文件、类、ID、公开导出和 BOX gesture 分支，同时保留 Crop Lasso、Crop Polyline 与 Cutout Lasso 的公共 Selection 交互；用搜索和交互测试验证边界
- [x] 4.3 从 `AnyImageSettings`、设置同步和工具栏绘制中删除 `crop_box_refine_selection`、`crop_box_invert`、`crop_box_keep_original`，确认 Frame 无业务选项且其他三个 Crop 子工具的独立设置不变

## 5. 文档与完整验证

- [x] 5.1 更新用户文档、架构、Operator 索引、Crop Tool 与公共 Viewport/Image 内部文档，用流程图正面描述 Frame 的多选图片、Viewport 分辨率、active 对象/深度基准、逐像素深度合成、输入对象消费、透明 Canvas、view-facing 结果和无选项行为，并移除当前功能描述中的 Crop Box
- [x] 5.2 运行 Crop、菜单、属性、注册、对象放置、打包与 Blender Addon 相关测试，再运行 `uv run pytest`，确认完整测试集通过且不构建文档或扩展产物

## 6. 试用反馈修正

- [x] 6.1 更新 proposal、design 与 Frame spec，明确 Viewport snapshot 分辨率、Preferences 最大长边、透明 RGB 边缘扩展、无重叠 warning 和原生点击选择语义
- [x] 6.2 实现 Frame 的 Viewport 像素输出尺寸和 `max_frame_resolution` Preferences，并补充远距离、Region 与配置上限测试
- [x] 6.3 统一投影结果的透明 RGB 边缘扩展，将 Frame 无 active overlap 降级为 warning，并补充像素及报告级别测试
- [x] 6.4 让 Frame、Crop Lasso、Cutout Lasso 使用 drag-only 交互，修正点选型工具的首次对象切换，并用 ToolDef 与交互测试覆盖普通点击、Shift 加选和拖动启动
- [x] 6.5 运行 Crop、Preferences、注册与 Blender Addon 相关测试，再运行 `uv run pytest`，确认完整测试集通过且不构建文档或扩展产物
- [x] 6.6 统一要求图片编辑源同时为 active 和 selected Image Empty，让 Frame 在无效 active 时报告 warning，并用 active 未选中、active 非图片但 Selection 含图片及正常混合 Selection 测试验证
- [x] 6.7 删除所有图片 WorkspaceTool 的 fallback selection 选项，以公共显式 keymap 保留普通点击与 Shift 点击选择，并验证 Tool Settings 不再暴露 `Drag: Select Box/Lasso`
