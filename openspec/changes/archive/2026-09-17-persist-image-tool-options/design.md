## Context

当前 `ImageBoxTool` 以 `group=True` 注册，Lasso、Line、Polyline 依次通过 `after` 加入同组；`ImagePerspectiveTool` 来自独立的 `perspective_tool/`，单独注册在该组之后；Cutout 再注册到 Perspective 后并带分隔。图片裁切因此在代码、工具栏和文档中分成 Image Tool 与 Perspective Tool 两套概念。

Box、Lasso、Line、Polyline 共用 `ImageSelectionGesture` 与 `EditImageMask`。Perspective 使用自己的 modal Operator，但最终同样创建裁切图片并调用 `replace_empty_image()`。Line 额外依赖共享 Viewport 中把一条直线转换为半平面多边形的分支。

Crop 选项尚未持久化。本地 Selection Crop 与 Perspective 都同步替换源对象；Box/Lasso 的 Refine Selection 在异步 Job 响应中替换源对象。Keep Original 必须覆盖四个最终 Crop 子工具的同步结果和两个可 Refine 子工具的异步结果。

Cutout 的 `BaseShape` 和 `O Image Cutout` 统一以局部 `+X` 为向内轴、YZ 为纸面；`CUTOUT_AXIS_TO_SOURCE` 把这套坐标映射到 Image Empty 的 XY 图片平面和 `-Z` 向内方向。结果世界位置正确，但 Mesh Object 的 local transform 与源 Empty 不同。Depth Surface 的 Object Space Normal 也按 `+X` 坐标编码。

## Goals / Non-Goals

**Goals:**

- 用一个 `crop_tool/` 业务边界承载 Box、Lasso、Polyline 与 Perspective，并在工具栏显示为一个四合一 Crop Tool 组。
- 彻底删除 Line 裁切和 Image / Perspective 的旧工具命名。
- 让 Crop Tool 组与 Cutout Tool 作为两个独立工具栏入口相邻。
- 分别保存四个 Crop 子工具的 Keep Original、三个 Selection Crop 子工具的 Invert 和 Box/Lasso 的 Refine Selection。
- 让 Selection Crop 从各自工具选项读取持久 Invert，不占用字母快捷键。
- 让本地和 AI Crop 共享一种 Keep Original 结果落地方式，并明确选择和 active object 状态。
- 让 Cutout 在不改变世界空间成品的前提下选择 `-Z` 或 `+X` 局部向内轴。

**Non-Goals:**

- 不为 Invert、Refine Selection、Keep Original 或 Inward Axis 增加 Crop 或 Cutout 字母快捷键。
- 不为 Crop Perspective 增加 Invert、Selection 或 Refine Selection 语义。
- 不改变 Crop 的 Selection 栅格化、Perspective 重采样、裁切 bounds 或结果图片内容。
- 不改变 Cutout 的 Shape Pie 或结果对象保留行为。
- 不把工具设置迁移为跨 `.blend` 文件的 Addon Preferences。

## Decisions

### 1. 统一迁移到 `crop_tool/` 并删除旧入口

将 Box、Lasso、Polyline、共享 Selection Crop Operator 与 Perspective 实现收拢到 `operators/crop_tool/`。WorkSpaceTool 使用 `CropBoxTool`、`CropLassoTool`、`CropPolylineTool`、`CropPerspectiveTool`，Tool ID 使用 `anyimage.crop_box`、`anyimage.crop_lasso`、`anyimage.crop_polyline`、`anyimage.crop_perspective`；Operator 和激活入口同步使用 Crop 动词与 `anyimage` 前缀。

删除 `image_tool/line.py`、`LINE` gesture、直线半平面构建函数及所有注册和文档。删除旧 `image_tool/`、`perspective_tool/` 路径、旧 Tool / Operator ID 和兼容导出。菜单中的 Image Tool 入口改为 Crop Tool，并默认激活 Crop Box。

相比只改 UI Label，这能让用户概念、源码目录、类名、公开 ID 和文档保持同一边界，符合项目不保留兼容层的约束。

### 2. 四个 Crop 子工具连续注册为一组，Cutout 作为第二个入口紧随其后

以 Crop Box 作为 `group=True` 的首项，Crop Lasso、Crop Polyline、Crop Perspective 依次通过前一个 Crop Tool ID 注册且不加 separator。完成 Crop 组注册后，直接调用 `register_tool(CutoutTool)`：不传 `after`、`group` 或 `separator`，使 Cutout 作为普通单项 ToolDef 追加在 Crop 组后，而不是 singleton tuple 或带分割线的入口。Cutout 使用 Blender Add UV Sphere 的 `ops.mesh.primitive_sphere_add_gizmo` 图标。卸载严格按 Cutout、Perspective、Polyline、Lasso、Box 的逆序执行。

注册测试直接验证工具类型、`after`、`group`、`separator` 和逆序注销，避免 Perspective 再次成为独立工具或 Cutout 被其他入口隔开。

### 3. 每个 Crop 子工具使用固定且唯一的 Scene 设置

`AnyImageSettings` 增加四个 `crop_*_keep_original`，以及 Box、Lasso、Polyline 三个 `crop_*_invert`；Box 与 Lasso 的 Refine Selection 设置同步改为 Crop 名称。所有布尔值默认关闭。Crop Perspective 只读取自己的 Keep Original，不声明或绘制 Invert / Refine Selection。

Selection Crop Operator 按 gesture 映射读取对应设置；Perspective Operator 直接读取自己的设置。固定映射比共享一个当前 Crop 状态更能保证切换子工具后恢复各自值，也便于逐项测试没有串用。

### 4. Crop Invert 只由工具选项控制，Cutout 不使用字母快捷键

Crop Box、Lasso、Polyline 的 WorkSpaceTool keymap 只保留鼠标启动操作，不注册 `F` 或其他字母键。共享 Crop Selection modal 删除现有 `F` 切换分支，每次开始手势时只读取当前子工具保存的 Invert。Crop Perspective 同样不注册选项快捷键；Cutout 删除现有 modal `F` 分支和对应状态提示。

### 5. 四个 Crop 子工具共用结果落地 helper

Keep Original 关闭时保持 `replace_empty_image(source_object, result_image, ...)` 路径。开启时，在结果就绪的 Blender 主线程复制源 Image Empty，将复制对象链接到源对象所在 Collection，再对复制对象调用同一图片替换逻辑。随后清理选择状态，选择并激活结果对象；未改变的源 Image Empty 保留但不继续选择。

Box、Lasso、Polyline 与 Perspective 都调用这个 helper，不各自实现对象复制。对象复制继承源变换和 Image Empty 显示属性；既有替换逻辑继续负责裁切尺寸、offset、图片用户数与命名。

### 6. 每次 Crop 冻结所属子工具的 Keep Original

Selection Crop 本地编辑与 Perspective 本地编辑分别把当前子工具的 Keep Original 传给结果落地 helper。Box/Lasso 启动 Refine Selection Job 时把该布尔值作为隐藏 Blender Operator Property 传入，并在响应阶段使用；不修改跨进程 Job request。

这保证异步执行期间切换工具设置不会改变已提交结果，也不会让一个 Crop 子工具读取另一个子工具的状态。

### 7. Cutout 在最终几何边界转换 Inward Axis

为 Cutout 增加 `NEGATIVE_Z` / `POSITIVE_X` Scene EnumProperty。保留 `BaseShape`、Depth 标定与 `O Image Cutout` 内部现有 `+X` 计算约定，只在节点组最终 Geometry 输出和对象矩阵边界应用选项：

- `+X` 使用现有 Geometry 输出与 `source_matrix @ crop_translation @ CUTOUT_AXIS_TO_SOURCE` 对象矩阵；
- `-Z` 在节点组末端用 `CUTOUT_AXIS_TO_SOURCE` 把最终 Geometry 转为 XY 纸面、`-Z` 向内，再使用 `source_matrix @ crop_translation` 对象矩阵。

两条路径的世界坐标都等于 `source_matrix @ crop_translation @ CUTOUT_AXIS_TO_SOURCE @ internal_geometry`，因此位置、大小、UV 和正反面保持一致。节点组增加由创建代码设置的 Inward Axis 输入，构建脚本、资产验证和接口测试同步更新；修改器输入保持 `SINGLE`。

### 8. Object Space Normal 随 Cutout 局部坐标转换

Depth Surface 的 Object Space Normal 文件继续由 Server 按内部 `+X` 约定生成，不扩展 Job 协议。选择 `-Z` 时，Blender 在结果导入边界把解码后的法线从 `(x, y, z)` 转为 `(-y, z, -x)` 并重新编码后 Pack；`+X` 直接使用现有图片。Tangent Space Normal 不依赖对象局部坐标轴，不执行转换。

### 9. UI 与状态文本只描述当前 Crop 子工具

Crop Box、Lasso、Polyline 的状态文本描述各自 Invert On/Off，但不提示字母快捷键；Crop Perspective 保留四点与宽高比交互提示，不显示 Invert。Invert、Refine Selection、Keep Original 与 Inward Axis 只通过工具设置 UI 修改。README 和内部 Operator 索引统一使用 Crop Tool；原 Image Tool 与 Perspective Tool 文档合并为 `crop-tool.md`。

## Risks / Trade-offs

- [旧 Workspace 保存了已删除的 Tool ID] → 不保留兼容 Tool；扩展注册后由 Blender 回退到可用工具，用户重新选择 Crop Tool。
- [Perspective 加入分组后入口发现性变化] → 使用明确的 Crop Perspective 名称和原有图标，并在 Crop Tool 文档中与三个 Selection Crop 并列说明。
- [删除 Line 影响既有使用习惯] → 这是明确的产品删除；不模拟半平面兼容行为，Polyline 继续承担自定义边界裁切。
- [四个 Keep Original 或三个 Invert 设置发生串用] → 每个 WorkSpaceTool 使用固定唯一的 Scene Property，参数化测试逐项切换并验证其余值不变。
- [复制对象可能遗漏 Collection 归属] → 明确链接到源对象的 Collection，并用测试验证结果与源位于预期 Collection。
- [异步 Refine 完成时源对象已被用户删除] → 沿用现有按名称解析源对象的失败处理，不创建失去来源的结果对象。
- [Keep Original 连续使用会创建大量对象和图片] → 这是选项的显式产物语义，默认关闭，不增加自动清理。
- [Inward Axis 同时影响 Geometry、对象矩阵和 Object Space Normal] → 在创建入口冻结一次选项值，并以相同值设置三处；覆盖四种 Shape、非均匀源变换和 Normal 的世界空间对照测试。
- [节点资产接口变化导致旧资产与代码不匹配] → 同步构建脚本、资产文件、结构验证与打包测试，不保留缺少新输入的兼容分支。

## Migration Plan

实施时先迁移 Crop 模块与名称、删除 Line，再切换注册和菜单入口，避免同一版本同时注册新旧 Tool ID。四个 Crop Keep Original 和三个 Invert 使用关闭默认值，因此旧文件加载后保持原有裁切结果语义，但不会迁移尚不存在的旧设置名称。Cutout Inward Axis 默认 `-Z`，会有意改变新建 Cutout 的 local transform；选择 `+X` 可取得旧坐标约定。

部署时同步代码与重建后的 `assets/O_AnyImage.blend`，不支持新代码搭配旧节点资产。回滚需要恢复旧模块、注册与节点资产；已创建的 Crop 结果和 Cutout Mesh 不会被自动迁移。
