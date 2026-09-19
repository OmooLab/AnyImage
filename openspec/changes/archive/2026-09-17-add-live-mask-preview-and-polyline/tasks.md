## 1. Mask 设置与 Selection 精简

- [x] 1.1 将 Mask Mode 默认值改为 Subtract，在 Gesture 中增加 Polyline，并更新 Scene Property、Operator 与 Tool Settings 测试
- [x] 1.2 删除 `SelectionPath.invert`、JSON `invert` 字段、完整画布反选 bounds 和补集栅格化分支，使 Cutout 序列化只传递 points
- [x] 1.3 清理测试中遗留的 Keep Original、Refine Selection 参数及重复历史缺席断言，以当前 Property、Operator、Job 和打包内容的精确集合固定公开边界
- [x] 1.4 更新 Selection 与 Cutout 测试，验证局部抗锯齿 bounds、JSON 往返、整图 Cutout 和普通 Lasso 在精简后保持正确

## 2. Polyline Gesture

- [x] 2.1 在无 Crop 术语的 `ImageGesture` 中实现 Polyline 点提交、移动预览、8 px 起点闭合、Enter 完成、Backspace 回退和取消状态机
- [x] 2.2 为 Polyline 绘制闭合预览、虚线轮廓和起点指示，并更新 Mask 状态文字与 Radius 显示条件
- [x] 2.3 将完成的 Polyline 接入 Lasso 共用的 SelectionMask 与 Alpha 合成入口，验证 Set、Add、Subtract、画布保持和对象点选语义
- [x] 2.4 补充 Polyline Modal、Overlay、闭合方式、无效路径、取消和工具切换测试

## 3. Brush Footprint 与 Alpha

- [x] 3.1 将 Alpha 公式整理为完整 Selection 共用的纯函数，固定 Set、Add、Subtract 结果
- [x] 3.2 从简化后的屏幕轨迹生成圆形采样点和等宽连接条，并在 screen space 与图片空间分别执行同语义 union
- [x] 3.3 删除逐 Primitive Mask 列表和失去调用方的 `merge_selection_masks()`，图片空间只保留一个累计覆盖画布
- [x] 3.4 补充单击、稀疏移动、急转折返、自交、倾斜/缩放投影与图片边界测试

## 4. Brush 虚线预览与延迟提交

- [x] 4.1 删除临时 Image、dirty RGBA、30 FPS Flush 与实时 Pixel Buffer 更新，使 Brush 拖动阶段不读取或修改 Image
- [x] 4.2 将 Brush Primitive 在 screen-space scanline bands 中融合，消除内部交错边、急转尖角和未填充三角，并复用 Lasso、Polyline 的填充配色
- [x] 4.3 让 Overlay 与鼠标释放后的 Selection 栅格化复用同一组 Primitive 与 union 语义，再通过公共 Alpha 与 Image 替换入口一次性提交
- [x] 4.4 取消、异常与工具切换只结束 Overlay，不创建临时 Image 或恢复分支，并保持对象 identity、transform、画框和单步 Undo
- [x] 4.5 更新 Brush 急转折返、Primitive Union、融合外轮廓、Overlay 配色、释放提交和真实 Blender Image 生命周期测试

## 5. 文档与验证

- [x] 5.1 更新 README 与 Image Edit、Common、Cutout 内部文档，说明三种 Gesture、Subtract 默认值、Brush Mode 填充、Primitive Union、释放提交和只含 points 的 SelectionPath
- [x] 5.2 搜索并清除运行时与文档中的 Keep Original、Refine Selection、Selection Invert、旧 Brush 全轨迹合并 Helper 和历史 Crop Polyline 名称
- [x] 5.3 运行 Selection、Blender Addon、Cutout、Image Edit 与 Packaging 定向测试并修正失败
- [x] 5.4 运行 `uv run pytest` 和 OpenSpec strict validation，不构建文档、节点资产或发布产物
