## 1. Crop Tool 重组

- [x] 1.1 将 Box、Lasso、Polyline、共享 Selection Crop 与 Perspective 实现迁移到 `operators/crop_tool/`，统一类名、Tool ID、Operator ID、激活入口和导出为 Crop 术语；用导入、注册和 ID 测试验证旧 `image_tool/`、`perspective_tool/` 路径及旧公开 ID 不再存在
- [x] 1.2 删除 Image Line WorkSpaceTool、`LINE` gesture、半平面多边形函数及对应状态和测试分支；用搜索与交互测试验证 Crop Tool、菜单和公开 Operator 不再提供 Line
- [x] 1.3 按 Crop Box、Crop Lasso、Crop Polyline、Crop Perspective 注册一个连续 WorkSpaceTool 组，再将不传 `after`、`group`、`separator` 的普通单项 Cutout Tool 紧接该组并使用 Add UV Sphere 图标；用 Blender 实际工具结构和注册测试验证工具类型、图标、顺序及严格逆序注销
- [x] 1.4 将 AnyImage 图片编辑入口改名为 Crop Tool 并默认激活 Crop Box；用菜单和 Operator 测试验证显示名、描述与激活目标

## 2. 独立工具设置与 Invert

- [x] 2.1 为四个 Crop 子工具增加唯一的 Keep Original Scene Property，为 Crop Box、Lasso、Polyline 增加唯一的 Invert，为 Box/Lasso 保留改为 Crop 名称的 Refine Selection，并为 Cutout 增加默认 `-Z` 的 Inward Axis；用属性测试验证默认值、保存状态、四个 Keep Original 与三个 Invert 互不影响且 Perspective 没有 Invert
- [x] 2.2 扩展设置读取与工具栏绘制，让每个 Crop 子工具只显示自己的 Keep Original，三个 Selection Crop 显示各自 Invert，Box/Lasso 额外显示 Refine Selection，Crop Perspective 不显示 Selection 选项，Cutout 显示 Inward Axis；用工具设置测试验证属性顺序、名称与映射
- [x] 2.3 删除 Crop 与 Cutout Selection modal 的 `F` 切换分支，不为两个工具栏入口注册任何选项字母快捷键；用 keymap 与交互测试验证 `F` 不再切换选项
- [x] 2.4 更新 Crop 与 Cutout 的状态文本，不提示字母快捷键；用状态文本测试验证各工具的交互提示边界

## 3. 四个 Crop 子工具的 Keep Original

- [x] 3.1 增加 Crop 共用的 Image Empty 结果落地逻辑：关闭时替换源对象，开启时复制源对象承载结果、保留但取消选择源对象，并选择和激活结果对象；用对象与图片生命周期测试验证变换、显示设置、Collection、选择和命名行为
- [x] 3.2 将各自 Keep Original 接入 Box、Lasso、Polyline 本地裁切路径，并用参数化编辑测试验证默认替换、开启后保留源对象、连续裁切以新结果为输入且子工具状态互不串用
- [x] 3.3 将提交时的 Box/Lasso Keep Original 传入 Refine Selection Blender Operator 并在异步响应落地结果，不改变 Job request；用响应和 Undo 测试验证源对象保留、结果激活状态与异常清理
- [x] 3.4 将 Crop Perspective 的独立 Keep Original 接入透视结果落地；用 Perspective 交互与执行测试验证默认替换、开启后保留源 Empty 并激活结果，且不改变其他三个 Keep Original

## 4. Cutout Inward Axis

- [x] 4.1 将提交 Shape 时的 Inward Axis 固定到 Cutout Operator，并贯通本地与异步创建路径；用 Pie、Operator 和响应测试验证四种 Shape 都取得提交时的同一选项且 Job request 不增加该字段
- [x] 4.2 扩展 `O Image Cutout` 构建脚本，在最终 Geometry 边界按 Inward Axis 切换 `-Z` 与 `+X` 坐标约定，并同步 `assets/O_AnyImage.blend`、结构验证和节点资产文档；运行 `uv run build_node` 验证资产
- [x] 4.3 调整 Cutout 对象矩阵，使默认 `-Z` 使用源 Image Empty 的 local transform、`+X` 保留现有轴变换；用四种 Shape、裁切范围及旋转和非均匀缩放源对象测试验证两种选项的对应世界空间点重合
- [x] 4.4 在 `-Z` 模式导入 Depth Surface Object Space Normal 时执行 `(-y, z, -x)` 通道转换，保持 `+X` 与 Tangent Space 路径不变；用法线像素和材质着色方向测试验证两种坐标约定

## 5. 文档与回归验证

- [x] 5.1 将原 Image Tool 与 Perspective Tool 内部文档合并为 `docs/internals/operators/crop-tool.md`，用流程图说明四合一工具组、三个独立 Invert、四个独立 Keep Original 及同步和异步结果分支，并更新 Operator 索引与公共 Viewport 文档
- [x] 5.2 更新 README、`docs/index.md`、架构和相关用户表达，统一使用 Crop Tool / Crop Box / Crop Lasso / Crop Polyline / Crop Perspective，确认没有 Image Line、Image Tool 或独立 Perspective Tool 的当前功能描述
- [x] 5.3 更新 `docs/internals/operators/cutout-tool.md`，使用流程图说明内部 `+X` 几何、最终 Inward Axis 转换、对象矩阵与 Object Space Normal 的对应关系
- [x] 5.4 运行 Crop、Cutout 交互与对象、属性、菜单、注册、节点资产、打包和 Blender Addon 相关测试，再运行 `uv run pytest`，确认完整测试集通过
