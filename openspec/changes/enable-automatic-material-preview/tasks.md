## 1. 共用偏好与视图逻辑

- [x] 1.1 在 `PreferencesLite` 的 Tools 区添加默认开启的 `auto_material_preview`，补齐共用界面翻译，并验证完整版和 Lite 的默认值与显示。
- [x] 1.2 在 `common/viewport.py` 实现 `apply_material_preview`，按偏好、传入视图和当前模式更新对应属性。

## 2. 接入结果应用入口

- [x] 2.1 在本地与 AI 共用的 `create_cutout_shape` 中，紧邻 `create_shape_object` 调用前应用预览。
- [x] 2.2 在 Convert to World 同步转换成功处和 Convert to Panorama 响应成功处应用预览，并启用最终模式的 Scene World。

## 3. 验证

- [x] 3.1 用参数化测试覆盖四种着色模式、开关关闭和无 3D 视图，检查两种模式独立的 Scene World、Scene Lights 及其他视图设置。
- [x] 3.2 在相关 Operator 测试中验证本地及 AI Cutout 的触发时机、两种环境转换的成功与取消路径，并用两个 3D 视图验证异步操作只调整发起视图。运行相关偏好、视图和 Operator 测试。
