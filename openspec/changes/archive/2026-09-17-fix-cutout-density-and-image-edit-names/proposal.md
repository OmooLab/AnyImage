## Why

Cutout 的 Mesh Detail 先按源图像素间距计算，却又按 Selection bounds 的原始像素尺寸缩小网格分辨率，导致 Upscale 后的新增像素无法转化为对应的网格细节。Remove Background、Upscale 与 Crop 同属直接编辑 Image Empty 的工作流，但共享 Image 数据时分别出现 `_color` 后缀或丢失 `.png` 扩展名，说明结果创建仍混用了材质贴图命名与旧的基础名逻辑。

## What Changes

- 让 Cutout 的 Low、Medium、High、Ultra 始终分别保持 32、16、8、4 个源图像素的采样间距；Upscale x4 后，同一图像范围在线性方向获得约 4 倍采样密度，直到实际网格采样数量触及配置上限。
- 将 **Maximum Cutout Mesh Resolution** 只应用于实际网格采样长边，不再把 Selection bounds 的原始像素长边当作待缩放的图片输入尺寸。
- 统一 Remove Background、Upscale、Crop Box、Crop Lasso、Crop Polyline 与 Crop Perspective 的纯 Image 编辑结果命名：始终以源 Image 数据块的完整名称请求新名称，保留 `.png` 等原有格式文字，不主动添加 `_color` 等材质贴图后缀。
- 允许 Blender 在源 Image 仍被共享时自动追加 `.001` 等唯一性后缀；代码不自行模拟、剥离或改写该后缀。
- 收拢纯 Image 编辑结果的创建、加载、命名与替换入口，使材质 Color、Depth、Normal 的派生贴图命名只留在 Plane、Cutout 等材质工作流。
- 删除原有错误的 Image 添加逻辑、旧入口和调用方修补，不保留可选后缀参数、转发函数或兼容层。

## Capabilities

### New Capabilities

- `cutout-mesh-sampling`: 规定 Cutout Mesh Detail 的源像素采样间距、Upscale 后的密度变化及实际网格分辨率上限。
- `image-edit-results`: 规定直接编辑 Image Empty 的结果数据块命名、共享引用分流以及与材质贴图命名的边界。

### Modified Capabilities

无。

## Impact

- 影响 `operators/cutout_tool` 的网格分辨率计算及对应几何、交互测试。
- 影响 `common/image.py` 中 Image 编辑结果的创建、加载、命名和 Empty 替换职责，以及 Remove Background、Upscale、Crop Selection、Refine Crop、Crop Perspective 的调用路径；旧的错误创建入口及无用导入会被移除。
- Plane、Depth Plane、Cutout Shape 使用的 `_color.png`、`_depth.exr`、`_normal.png` 材质贴图命名保持不变。
- 需要同步 Common、Crop Tool、Cutout Tool 与相关运行时文档；不新增依赖或 Server 协议。
