## ADDED Requirements

### Requirement: Frame replaces Crop Box
系统 SHALL 以 **Frame** 替换 **Crop Box**，并 SHALL 在 Crop Tool 组中按 Frame、Crop Lasso、Crop Polyline、Crop Perspective 的顺序注册四个子工具。Frame 的显示名称、Tool ID、Operator、激活入口、源码边界和文档 SHALL 统一使用 Frame 术语，不得保留 Crop Box 的公开入口或兼容名称。

#### Scenario: User opens the Crop Tool group
- **WHEN** 用户展开 Crop Tool 组
- **THEN** 首个子工具显示为 Frame
- **AND** 其后依次为 Crop Lasso、Crop Polyline 和 Crop Perspective
- **AND** 工具组中不再显示 Crop Box

#### Scenario: User activates the crop entry
- **WHEN** 用户从 AnyImage 菜单激活 Crop Tool
- **THEN** 系统激活 Frame

### Requirement: Frame defines the complete output canvas
Frame SHALL 将用户在当前 3D Viewport 中拖出的矩形定义为结果图片的完整矩形 Canvas。该矩形可以小于或大于选中 Image Empty 的当前屏幕投射范围；Canvas 位于所有参与源投射范围外的像素 SHALL 使用透明 RGBA，系统 SHALL NOT 根据可见 Alpha 再次紧裁结果。

#### Scenario: User draws a smaller frame
- **WHEN** 用户围绕选中 Image Empty 当前投射的一部分拖出 Frame
- **THEN** 结果图片只包含 Frame 内采样到的投射图案
- **AND** 结果 Canvas 严格对应用户所画 Frame

#### Scenario: User draws a larger frame
- **WHEN** 用户拖出的 Frame 超出所有参与 Image Empty 的当前投射范围
- **THEN** 结果图片保留 Frame 的完整范围
- **AND** 未被源投射覆盖的区域为透明
- **AND** 系统不移除这些透明边缘

### Requirement: Frame bakes and composites selected viewport projections
Frame SHALL 使用完成矩形手势时的 Viewport 投影、视图朝向、区域尺寸和每个参与 Image Empty 的世界变换，把所有参与图片的当前投射重采样为结果 RGBA。每个输出像素 SHALL 按观察射线上的几何深度将有效样本从远到近排序，再使用预乘 Alpha source-over 合成；active Image Empty SHALL 在相同深度的样本中位于其他参与对象之上。采样 SHALL 使用预乘 Alpha 插值，源图片范围外 SHALL 采样为透明。

#### Scenario: One selected image is oblique to the view
- **WHEN** 倾斜的选中 Image Empty 在当前透视视图中呈现为梯形投射，用户完成 Frame
- **THEN** 结果图片烘焙该梯形投射在 Frame 内的当前可见外观
- **AND** 操作完成瞬间的屏幕图案与操作前一致

#### Scenario: Selected images overlap in depth
- **WHEN** 多个参与 Image Empty 的投射在 Frame 内重叠
- **THEN** 系统逐像素按空间深度从远到近合成 RGBA
- **AND** 较近图片的透明区域仍显示后方图片

#### Scenario: Active image overlaps another image at the same depth
- **WHEN** active Image Empty 与另一参与对象在同一深度产生重叠样本
- **THEN** active Image Empty 的样本合成在另一对象之上

#### Scenario: Frame extends beyond the projected source
- **WHEN** Frame 同时覆盖参与源投射内部和外部区域
- **THEN** 系统重采样并合成内部的源 RGBA
- **AND** 系统为外部区域写入透明 RGBA

#### Scenario: Frame has no active projection overlap
- **WHEN** 完成的 Frame 与 active Image Empty 的屏幕投射没有几何重叠
- **THEN** 系统以 warning 提醒用户
- **AND** 系统取消操作并保留所有选中对象不变

### Requirement: Viewport defines output resolution
Frame SHALL 使用所画矩形在当前 Region 中的屏幕像素宽高作为结果尺寸依据，并 SHALL 保持 Frame 的屏幕宽高比。结果宽高 SHALL NOT 超过当前 Region 对应维度，最长边 SHALL NOT 超过 Preferences 中可配置的 Frame 最大长边。active 或其他参与图片的原始分辨率、对象距离和透视缩放 SHALL NOT 直接放大结果尺寸。

#### Scenario: Other selected image has a higher resolution
- **WHEN** 非 active 参与图片的分辨率高于 active 图片
- **THEN** 结果尺寸仍只由当前 Viewport 中的 Frame 像素尺寸决定
- **AND** 非 active 图片重采样到该结果 Canvas

#### Scenario: Frame is drawn around a distant image
- **WHEN** active Image Empty 距离视角很远或投射尺度很小
- **THEN** 结果尺寸仍对应 Frame 的当前屏幕像素尺寸
- **AND** 对象距离不会产生超出 Viewport 分辨率的图片

#### Scenario: Frame exceeds the configured maximum
- **WHEN** Frame 屏幕像素最长边超过 Preferences 配置上限
- **THEN** 系统等比限制结果尺寸
- **AND** 结果宽高比继续对应 Frame

### Requirement: Transparent output edges avoid black interpolation
Frame SHALL 保持未覆盖区域的 Alpha 为 0，并 SHALL 使用相邻可见颜色扩展紧邻可见内容的透明像素 RGB。颜色扩展 SHALL NOT 改变任何像素的 Alpha 或 Frame Canvas 范围。

#### Scenario: Projected image ends inside the frame
- **WHEN** 不透明或半透明图片边缘外侧是 Frame 的透明区域
- **THEN** 外侧像素 Alpha 保持为 0
- **AND** 线性纹理插值不会因外侧 RGB 0 形成明显黑边

### Requirement: Frame creates a view-facing Image Empty
Frame SHALL 使用 active Image Empty 的原 Blender Object 承载结果 Image，并更新其世界变换和 Image Empty 显示范围，使本地 XY 图片平面平行于操作完成时的 Viewport 视平面、本地正面朝向该视角，且结果矩形在该视角中覆盖用户所画 Frame。结果平面 SHALL 位于穿过 active Image Empty 世界原点、并与视平面平行的深度平面上。

#### Scenario: User finishes a frame in perspective view
- **WHEN** 用户在透视 Viewport 中完成 Frame
- **THEN** 结果 Image Empty 朝向操作时的视角
- **AND** 结果四边在该视角中对应 Frame 的四边
- **AND** 结果使用 active Image Empty 世界原点所在的视图深度

#### Scenario: User finishes a frame in orthographic view
- **WHEN** 用户在正交 Viewport 中完成 Frame
- **THEN** 结果 Image Empty 平行于该正交视平面并覆盖 Frame
- **AND** 烘焙后的图案保持操作时的屏幕外观

### Requirement: Frame operates on selected still Image Empties
Frame SHALL 以当前 Selection 内的 active still Image Empty 为基准对象，并将所有选中的 still Image Empty 作为参与源；选中的非 Image Empty 对象 SHALL 被忽略。Frame SHALL 允许矩形手势从 Viewport 任意位置开始。active object 未被选中、不是 still Image Empty、任一选中 Image Empty 不是 still image、Frame 尺寸无效或任一参与投影无法稳定求解时，系统 SHALL 取消整个操作并保持所有对象不变。

#### Scenario: User starts outside the source projection
- **WHEN** active object 是 still Image Empty，且用户从源投射范围外开始拖出一个与源投射相交的 Frame
- **THEN** 系统使用 active Image Empty 及其他选中的 still Image Empty 完成 Frame 操作

#### Scenario: Active object is unsupported
- **WHEN** active object 不是 still Image Empty
- **THEN** Frame 不开始图片重采样、合成或对象替换
- **AND** 系统以 warning 提醒用户选择一个 active Image Empty

#### Scenario: Active image is not selected
- **WHEN** active object 是 still Image Empty，但它不属于当前 Selection
- **THEN** Frame 不进入矩形操作
- **AND** 系统以 warning 提醒用户选择 active Image Empty

#### Scenario: Selection contains images but active object is not an image
- **WHEN** Selection 含有 still Image Empty，但 active object 是非图片对象
- **THEN** Frame 不使用 Selection 中的其他图片作为隐式基准
- **AND** 系统以 warning 取消操作

#### Scenario: Selection contains a non-image object
- **WHEN** active object 是 still Image Empty，且 Selection 还包含非 Image Empty 对象
- **THEN** Frame 忽略非 Image Empty 对象
- **AND** 非 Image Empty 对象不参与合成或删除

#### Scenario: A selected Image Empty is animated
- **WHEN** 任一选中的 Image Empty 使用视频或图片序列
- **THEN** 系统取消整个 Frame 操作
- **AND** 所有选中对象保持不变

### Requirement: Frame has no edit options
Frame SHALL 始终让 active Image Empty 承载结果，并在结果完整创建和放置后删除其他参与合并的选中 Image Empty。整个替换与删除 SHALL 属于同一个 Undo 操作；失败时 SHALL 保留全部输入对象。Frame SHALL NOT 提供 Refine Selection、Invert 或 Keep Original。系统 SHALL 删除 Crop Box 对应的 `crop_box_refine_selection`、`crop_box_invert` 和 `crop_box_keep_original` Scene Properties；Crop Lasso、Crop Polyline 和 Crop Perspective 的独立选项 SHALL 保持不变。

#### Scenario: User opens Frame settings
- **WHEN** 用户激活 Frame
- **THEN** 工具设置不显示 Refine Selection、Invert 或 Keep Original

#### Scenario: User completes a frame
- **WHEN** Frame 成功生成结果
- **THEN** active Blender Object 改为承载合成结果 Image 和新的视平面对齐变换
- **AND** 其他参与合并的 Image Empty 被删除
- **AND** 被忽略的非 Image Empty 对象保持不变

#### Scenario: Multi-image merge is undone
- **WHEN** 用户撤销一次成功的多图 Frame
- **THEN** active Image Empty 恢复操作前的 Image 与变换
- **AND** 其他被删除的参与 Image Empty 恢复

#### Scenario: Existing file contains removed Crop Box properties
- **WHEN** 扩展加载曾保存 Crop Box 选项的 `.blend` 文件
- **THEN** 运行时不注册或读取这些已删除属性
- **AND** 其他 Crop 子工具的设置仍按各自属性工作

### Requirement: Image tools preserve ordinary click selection
Frame、Crop Lasso 与 Cutout Lasso SHALL 只在鼠标发生拖动后启动图片手势，普通点击 SHALL 使用 Viewport 对象选择行为。Polyline 与 Perspective 首次点击另一对象时 SHALL 只切换 active selection，不开始图片编辑。图片工具 SHALL NOT 启用或显示 Blender fallback selection 的 Drag 设置。

所有图片编辑手势 SHALL 只在 active object 是当前 Selection 内的 Image Empty 时启动；否则系统 SHALL 以 warning 取消该次手势。

#### Scenario: User clicks another Image Empty while Frame is active
- **WHEN** 已有一个 active Image Empty，用户普通点击另一 Image Empty
- **THEN** Blender 按原生规则选择该对象并使其 active
- **AND** Frame 不开始、不显示矩形 Overlay，也不生成图片

#### Scenario: User shift-clicks another object
- **WHEN** 任一图片工具处于 active，用户 Shift 单击另一对象
- **THEN** Blender 保留原生追加或切换选择行为

#### Scenario: User drags while Frame is active
- **WHEN** 用户按住左键并移动到 Blender 的 drag threshold 之外
- **THEN** Frame 才收集当前 Selection 并进入矩形操作

#### Scenario: User opens image tool settings
- **WHEN** 用户激活 Frame、Crop Lasso、Crop Polyline、Crop Perspective 或 Cutout Lasso
- **THEN** Tool Settings 不显示 `Drag: Select Box/Lasso` 等 fallback selection 设置
