## 1. Image Empty 工具入口

- [x] 1.1 增加轻量 WorkspaceTool 激活 Operator，并在 `AnyImageImageMenu` 中显式平铺四个入口
- [x] 1.2 仅在 3D View 的 Image Empty `AnyImage` 菜单顶部显示四个工具入口，以分隔线突出 Cutout 并保持普通 Operator 文字对齐

## 2. 工具栏分组

- [x] 2.1 调整 `tools.TOOLS`，使 Cutout、Frame、Mask、Rectify 按顺序共用一个工具栏组

## 3. 验证

- [x] 3.1 更新菜单测试，验证四个工具入口的顺序、Tool ID、执行方式和区域限制
- [x] 3.2 更新注册测试，验证四个 Tool 的顺序、Cutout 分组参数及逆序注销
- [x] 3.3 运行相关测试和全量测试
