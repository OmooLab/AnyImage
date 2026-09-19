## 1. Cutout 手势

- [x] 1.1 在 properties.py 添加默认 Lasso 的 Cutout Gesture 属性并接入 Scene、Operator 和工具设置，检查注册与逆序注销测试。
- [x] 1.2 将 Cutout 接入共用 Polyline 启动、预览与完成逻辑，更新状态文本；覆盖逐点、闭合、双击、Enter、Backspace、取消、Lasso 回归和空白处源对象保持行为。

## 2. Uniform 初始化与资产

- [x] 2.1 将本次 Gesture 快照从选区提交经 Shape 菜单传入转换 Operator 和对象创建链路；覆盖异步期间切换设置的行为。
- [x] 2.2 为 Polyline 创建的 Depth Solid 设置 Mode 为 Uniform，验证 Lasso 与其他 Shape 的初始化行为。
- [x] 2.3 将节点内部 Uniform Thickness 默认值改为 0.5，检查同名 Thickness socket 的赋值目标并更新资产修订号；补充资产默认值与实际修改器值测试。
- [x] 2.4 运行 `uv run node-group build`，更新并验证 O_AnyImage.blend，确认源码与保存资产的 Capture Attribute 数量为零。

## 3. Mask 模式

- [x] 3.1 将 Mask 的 ADD / Add 统一改为 EXTEND / Extend，保持枚举数值与 Alpha 运算语义，将共用模式属性默认值改为 SET。
- [x] 3.2 更新模式、状态文本、设置持久化和注册测试，验证三种模式的 Alpha 结果及 RGB 保持行为。

## 4. 验证

- [x] 4.1 运行相关测试及 `uv run pytest`，确认正常退出。
- [x] 4.2 检查运行时代码和测试中的旧 Mask 模式引用及最终差异，确认源码、测试和节点资产一致。
