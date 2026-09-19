## 1. Image Edit 模块与工具注册

- [x] 1.1 确认 `standardize-cutout-z-axis` 已完成并以其最终 Cutout 主链、测试和文档作为实施基线
- [x] 1.2 将 `operators/crop_tool/` 迁移为 `operators/image_edit_tool/`，建立 Frame、Mask、Rectify 内容边界并删除 Polyline 文件与导出
- [x] 1.3 将类名、Operator ID、Tool ID、激活入口和状态文字改为 Image Edit、Mask、Rectify 当前术语，不保留旧 Crop 注册或兼容层
- [x] 1.4 更新扩展注册与逆序注销，补充测试验证 Frame、Mask、Rectify、Cutout 的顺序及旧工具完全缺席

## 2. Mask 设置与 Alpha 合成

- [x] 2.1 增加持久化的 Mask Gesture、Mode 和 Radius Scene Property，默认使用 Lasso、Set、25 px，并删除旧 Lasso/Polyline Refine、Invert 和 Keep Original 属性
- [x] 2.2 实现统一 Alpha 合成函数，按 Set `A × M`、Add `max(A, M)`、Subtract `A × (1 - M)` 修改 Alpha并原样保留 RGB
- [x] 2.3 用硬边、分数边缘、连续重复编辑、Add 恢复透明区域和全透明结果测试固定三种 Alpha 公式
- [x] 2.4 实现单一 Mask WorkSpaceTool 的 Tool Settings，以 Lasso/Brush 切换 Gesture、以三个展开图标切换 Mode，并仅在 Brush 下显示 Radius

## 3. Lasso 与 Brush 手势

- [x] 3.1 将公共 Crop/Polyline modal 拆为无 Crop 术语的图片手势基础能力，让 Mask Lasso 与 Cutout Lasso 只复用路径采样和图片平面投影
- [x] 3.2 为 Mask Lasso 接入统一 SelectionMask 与 Alpha 合成入口，删除 Refine Job、Invert、紧裁切和空 Alpha 拒绝分支
- [x] 3.3 实现屏幕像素 Radius 的 Brush 圆环、单击圆形印记和连续拖动胶囊覆盖，并将图片外笔画裁到当前画布
- [x] 3.4 补充 Brush 单击、稀疏移动连续性、倾斜/缩放图片投影、画布边界、Radius 显示和设置冻结测试
- [x] 3.5 让 Lasso 与 Brush 创建同尺寸 packed Image 并直接替换 active Image Empty，测试对象身份、matrix、display size、offset、共享源图片和单步 Undo 保持正确

## 4. Rectify 与结果替换

- [x] 4.1 将 Perspective 文件、类、ID、标签、状态、warning、Undo 和测试统一改为 Rectify，同时保留四点 Quad、预览、宽高比、Homography 和输出限制
- [x] 4.2 删除 Rectify 的 Keep Original 设置与 Operator 参数，使结果始终由 active Image Empty 承载
- [x] 4.3 保留 Rectify 的可见 Alpha trim 与 placement 行为，并用既有像素、交互和对象对齐测试验证改名未改变结果
- [x] 4.4 删除不再有调用方的结果复制 helper 和测试，让 Mask、Rectify 直接复用公共图片替换入口

## 5. 删除 Refine Selection

- [x] 5.1 删除 Cutout Tool Settings、Pie 传值、Operator Property、AI readiness 和请求中的 Refine Selection，仅以 Depth 或 Normal 判定是否提交 Job
- [x] 5.2 简化 Cutout Blender 响应和 Server Job，使本地、Depth、Normal 分支使用原始 Selection bounds 输入并继续由本地 SelectionMask 约束最终 Shape
- [x] 5.3 删除 `refine-image-selection` 注册、专用 Job、Server selection 封装、SelectionMask sidecar 序列化和无调用方的清理代码
- [x] 5.4 更新 Server、Cutout、打包和模型测试，验证 Refine 参数与文件缺席，同时 Remove Background、BEN2 Debug、模型缓存和 BEN2 包内容保持可用

## 6. 文档与完整验证

- [x] 6.1 更新 README、用户索引、架构、公共模块、Operator 索引及 Image Edit、Cutout、Runtime、Output 文档，只正面描述 Frame、Mask、Rectify 当前实现
- [x] 6.2 搜索并清除图片编辑业务中遗留的 Crop Lasso、Crop Polyline、Crop Perspective、Refine Selection、Invert、Keep Original 名称与旧 ID
- [x] 6.3 运行 Selection、Blender Addon、Cutout、Server Runtime、Packaging 定向测试并修正失败
- [x] 6.4 运行 `uv run pytest` 完整验证，不构建文档、节点资产或发布产物
