## 1. 快捷键与执行边界

- [x] 1.1 将 3D View 与 Node Editor 的图片粘贴绑定改为 `Shift+Ctrl/Cmd+V`，并删除 `Ctrl/Cmd+C` 跟踪绑定
- [x] 1.2 收紧 3D View 目标判断，只允许 Object Mode 与现有画笔纹理模式，其他模式返回不可用

## 2. 删除原生复制跟踪

- [x] 2.1 删除 `TrackNativeCopy`、进程内复制 token、粘贴分流判断及其导出和类型注册
- [x] 2.2 删除仅供复制跟踪使用的平台剪贴板变更 token 实现与相关导入

## 3. 测试与核查

- [x] 3.1 更新快捷键和扩展注册测试，验证每个目标编辑器仅注册独立图片粘贴组合
- [x] 3.2 更新上下文与执行测试，覆盖 Object、画笔、节点树以及 Pose、Grease Pencil 和其他不支持模式的避让行为
- [x] 3.3 运行相关测试，并用代码搜索确认旧 Operator、token、`Ctrl/Cmd+C` 跟踪引用均已移除
