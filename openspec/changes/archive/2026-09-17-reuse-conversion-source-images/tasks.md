## 1. 公共图像准备与材质配置

- [x] 1.1 在 common 中统一转换图像准备，复用其他 Empty 引用判断；测试覆盖独占、共享 Empty、隐藏或跨场景 Empty、仅材质共享和同路径不同 Image，并检查原名与副本命名。
- [x] 1.2 将材质配置改为配置已选定的 Image，审查全部材质创建调用点；运行材质测试，验证配置后 Image 身份、inverse / sRGB 回退、Alpha 配对及 Cutout、剪贴板行为。
- [x] 1.3 复用公共像素和状态辅助函数实现转换失败恢复；测试配置失败及配置成功后材质或对象创建失败，确认原图状态恢复与临时资源清理。

## 2. 转换入口和后端产物

- [x] 2.1 接入 Plane、Depth Plane、Relief Plane 的原图准备逻辑，保留 Plane 动画设置，并验证异步源对象与 Image 身份；通过转换测试确认引用身份、原始分辨率、帧参数和源图替换时取消应用。
- [x] 2.2 接入 Panorama，保留 HDR / 非 sRGB 分支和可保存的源像素；运行全景转换测试，覆盖独占与共享 Image、HDR 数值及 Alpha 模式。
- [x] 2.3 移除 Depth / Relief 和 Panorama 的冗余颜色输出及专用加载、复制辅助函数，清理导出和对应测试；通过 Job 测试验证产物集合，并用 rg 确认删除符号无残留业务引用。

## 3. 集成验证

- [x] 3.1 验证 byte、float、generated、dirty、packed 图像的透明 RGB 和保存重载行为，覆盖复用与复制两条路径，并验证转换 Undo / Redo 恢复对象及图像配置。Panorama HDR 往返通过；普通材质 float 使用 display 色彩空间重载的两项既有 xfail 保留。
- [x] 3.2 运行相关测试与 `uv run pytest`，确认正常退出；检查最终差异仅包含本变更实施内容，已有工作区修改保留，旧颜色路径与测试预期完成清理。全量结果：1125 passed、2 xfailed、52 subtests passed，退出码 0。
