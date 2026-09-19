## 1. Alpha 曲线与接口

- [x] 1.1 在 `material_layers.py` 的 O Image Layer 分支加入 Alpha Fix 输入及 Float Curve，按设计设置坐标、手柄、裁剪和连接。
- [x] 1.2 调整节点布局及未使用输出隐藏，在实际 Blender 节点编辑器检查总览与曲线局部。
- [x] 1.3 更新资产验证及对应测试，检查 socket 顺序、默认值、连接和曲线采样；覆盖强度 0、0.5、1、低 Alpha、端点、单调性与范围。

## 2. 材质创建联动

- [x] 2.1 在 `create_image_material()` 中复用偏好读取入口，为 O Image Layer 实例设置 Alpha Fix。
- [x] 2.2 补充材质行为测试，覆盖偏好开关、sRGB 回退、普通着色、Shadeless 及现有材质手动值保留，验证 O Image Depth Layer 的既有 Alpha 行为。

## 3. 验收

- [x] 3.1 对照参考图验证曲线形状，使用透明边缘图片比较强度 0、0.5、1 的效果，记录估计控制点的最终取值。
- [x] 3.2 按节点组专项规范同步 `docs/internals/node-assets.md` 的新输入与曲线说明。
- [x] 3.3 按用户授权更新 O Image Layer 节点资产，运行全量测试并确认正常退出，检查最终差异和接口引用；验证 Blender 节点资产，不构建文档或扩展发布包。

验证结果：766 passed、2 xfailed、50 subtests passed，退出码 0；Blender 4.5.10 资产验证与 OpenSpec 严格校验通过。
