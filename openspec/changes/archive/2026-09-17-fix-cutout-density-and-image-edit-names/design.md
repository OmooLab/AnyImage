## Context

Cutout 交互当前先把 Mesh Detail 换算为整张源图的 `mesh_resolution`，随后又把 Selection bounds 交给通用图片尺寸限制函数。后一步比较的是 bounds 原始像素数而不是预期网格采样数，因此在 Low 的 32 px 间距下，2048 px bounds 会被错误地当作超过默认 1024 网格上限并再次减半。

Image Empty 编辑已经共用替换与共享引用分流，但结果产生仍有两条旧路径：Job 结果使用面向材质的 Color 命名，本地像素结果使用去扩展名的基础名。替换逻辑只在旧 Image 可以被删除时把结果改回源名，所以共享引用会暴露两条路径的不一致。

## Goals / Non-Goals

**Goals:**

- 在 Cutout 全链路保留 Mesh Detail 的源像素间距语义，只对实际几何采样数量应用性能上限。
- 为直接 Image 编辑建立单一结果命名边界，使本地像素结果和 Job 文件结果一致。
- 明确分开 Image 编辑结果与材质派生贴图，删除错误的旧创建入口和调用方中的隐式命名修补。
- 使用真实 Blender 数据块测试覆盖共享与非共享源 Image。

**Non-Goals:**

- 不修改 BEN2、Upscale、Crop 的像素内容、文件编码、动画帧或 Server 协议。
- 不改变 Plane、Depth Plane、Cutout Shape 的材质贴图后缀。
- 不自行生成或解析 Blender 的 `.001` 数字唯一性后缀。

## Decisions

### 1. 保留像素间距，延后计算网格上限

Mesh Detail 在交互边界只产生 32、16、8、4 px 的采样间距，不再提前压缩为受 1024 限制的整图分辨率。Selection bounds 已知后，使用 `bounds 长边 ÷ 像素间距` 得到实际 Cutout 的预期采样长边；只有该值超过配置上限时才等比增大有效间距。几何层再根据源 Image 尺寸与 Image Empty 的世界尺度把有效像素间距换算为世界空间采样间距。

这比修补现有 `mesh_resolution × limited_image_size(bounds)` 公式更直接，因为配置项限制的是网格采样数量，不是可送入图片处理器的像素尺寸。也不采用简单 `min(整图 mesh_resolution, 上限)`，因为小 Selection 位于超大源图时仍应保持所选档位的像素间距。

### 2. 直接 Image 编辑结果始终请求完整源名

在 `common/image.py` 建立明确的 Image 编辑结果创建与加载入口。入口接收源 Image，并在创建或加载后把结果名称设置为 `source_image.name` 原值；旧 Image 尚存在时产生的数字后缀完全交给 Blender。`replace_empty_image()` 继续负责共享引用分流，并在旧 Image 可删除时把结果恢复为准确源名。

Remove Background 与 Upscale 改用 Image 编辑 Job 结果加载入口；三种 Selection Crop、本地 Crop、Refine Crop 和 Perspective Crop 改用同一像素结果创建入口。中间 BEN2 编码图不属于用户结果，可以继续使用临时名称并在响应结束时删除。

不采用在各 Operator 响应中分别写 `result_image.name = source.name`，因为这会继续保留重复逻辑，也无法保证本地 Crop 与异步 Job 的行为一致。

### 3. 材质派生贴图保留独立入口

`color_data_name()`、`depth_data_name()`、`normal_data_name()` 以及材质 Color Job 结果加载只服务 Plane、Depth Plane、Cutout Shape 等派生贴图工作流。若底层加载、Pack、颜色空间与序列设置需要复用，则由公共内部过程接收显式目标名；面向业务的两个公开入口仍分别表达“编辑原 Image”和“生成 Color 贴图”。

不把 `load_color_result_image()` 全局改为源名，因为 Convert to Plane 等调用方确实需要 `_color.png`，全局改名会把本次修复扩散为材质契约变化。

### 4. 删除错误的旧 Image 添加路径

迁移完成后直接删除旧的 Image 添加逻辑：面向 Crop 的旧基础名创建入口不保留默认或可选 `suffix` 形式，纯 Image 编辑也不再允许调用材质 Color 结果入口。同步清理 `image_base_name()` 等仅为旧路径存在的调用方导入、重复赋名和失去调用者的 helper；不添加别名、转发函数或弃用兼容层。

这比保留一个可同时表达“源图编辑”和“派生贴图”的宽泛函数更容易验证，也符合项目一次性迁移、不保留旧路径的约束。

### 5. 测试按可观察的数据块结果组织

纯函数测试验证 Mesh Detail 间距、bounds 实际采样数与上限；Blender 测试以同一 Image 被两个 Empty 引用和单一引用两种场景验证结果数据、名称与旧引用。Operator 测试分别覆盖 Remove Background、Upscale、Selection Crop（本地与 Refine）和 Perspective Crop 都调用统一入口，材质结果测试则确认 `_color` 等名称不变。

## Risks / Trade-offs

- [高分辨率小 Selection 不再被整图 1024 上限提前降密，局部网格可能比当前更多] → 仍按实际 Cutout 采样长边应用配置上限，并加入边界测试。
- [浮点 bounds 与取整可能令采样数相差一个点] → 对上限计算统一取整规则，规格只约束不超过上限和比例密度，不依赖具体三角形数量。
- [动画 Job 结果的 Image 名称可能保留 `.mp4` 等源名称文字] → 名称被定义为数据块身份而非结果文件格式；实际序列来源、Pack 和帧设置继续由加载入口配置。
- [重构公共加载入口误改材质 Color 命名] → 用独立公开入口和回归测试锁定 Image 编辑与材质贴图两种语义。

## Migration Plan

1. 先补充失败测试，分别重现 Upscale 后 Cutout 密度被抵消、共享 Image 出现 `_color` 和丢扩展名。
2. 调整 Cutout 参数传递与实际采样上限计算，移除把 bounds 当图片输入限制的路径。
3. 收拢 Image 编辑结果创建、加载和命名入口，迁移六类编辑工具调用方，同时保留材质贴图入口。
4. 删除错误的旧 Image 添加入口、参数、导入和调用方命名修补，不保留兼容转发。
5. 更新 Common、Crop Tool、Cutout Tool 文档并运行定向测试和全量测试。

本次只改变新执行结果，不迁移现有 `.blend` 中已经创建的数据块。若回退，代码可整体恢复；已有结果数据不需要转换。
