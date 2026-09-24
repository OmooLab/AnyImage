## 1. 图片对象标记

- [x] 1.1 将 Plane、Depth Plane、Relief Plane、Panorama 和全部 Cutout 创建路径的 `anyimage_mesh_shape` 替换为布尔标记 `o_image_object`
- [x] 1.2 删除源码与测试对旧标记及 Shape 字符串值的依赖，不增加兼容读取或迁移路径
- [x] 1.3 更新对象创建测试，验证所有 AnyImage 图片 Mesh 写入 `o_image_object = True`，普通 Mesh 不具备该标记

## 2. 对象图片目标

- [x] 2.1 实现受标记对象的 Color Image Texture 解析，覆盖普通、Depth/Relief 和 Panorama 材质拓扑，并拒绝歧义或已修改的未知拓扑
- [x] 2.2 扩展图片编辑目标捕获与验证，记录对象、材质槽、Material、Color 节点和 Image，且不跨编辑器回退
- [x] 2.3 在 Material 共享时为发起对象隔离材质，在 Image 共享时只替换当前 Color 节点，并沿用独占 Image 的原位更新
- [x] 2.4 补充对象目标解析、共享 Material、共享 Image、目标失效和 Undo/Redo 测试

## 3. 对象右键菜单

- [x] 3.1 增加对象 AnyImage 菜单，并仅在 3D View 与 Outliner 的活动 Mesh 带有 `o_image_object` 时显示
- [x] 3.2 在对象菜单复用现有 Remove Background、Upscale 和 AI 设置绘制逻辑，不显示 Delight
- [x] 3.3 让现有 Remove Background 与 Upscale Operator 从对象上下文解析目标，并保留服务忙碌与 Upscale 尺寸限制
- [x] 3.4 更新类型注册、逆序注销和菜单测试，覆盖受标记对象、普通 Mesh、Image Empty、无效材质及非目标编辑器

## 4. 验证

- [x] 4.1 运行相关普通 Python 与 Blender 测试，确认现有 Image Empty 和 Image Texture 节点操作没有回归
- [x] 4.2 检查旧标记与 Delight 实现引用均未进入本变更，并确认 OpenSpec 校验通过
