## 1. 原生选择策略

- [x] 1.1 为图片工具公共 selection keymap 增加明确的空命中 deselect 策略，保持 Frame 默认请求 deselect all
- [x] 1.2 让 `resolve_image_edit_click()` 在原生 Picker 空命中时保留 active object，同时保持命中另一对象时只完成原生选择
- [x] 1.3 将 Cutout 的普通点击配置为不在空命中时 deselect，并保持 Lasso、整图双击与 Shift toggle 的既有入口

## 2. 交互验证

- [x] 2.1 补充点击解析测试，覆盖空命中保留 active Image Empty、另一 Image Empty 和非图片对象保留原生选择结果
- [x] 2.2 补充 Mask 与 Rectify invoke 测试，验证透明或空白起点进入 Modal，而无有效 active Image Empty 时取消
- [x] 2.3 补充 Cutout keymap、Lasso 和整图双击测试，验证空白点击不清空 source、任意起点可进入既有提交链
- [x] 2.4 固定 Frame 仍以空白点击 deselect all，并验证 Shift 点击继续使用原生 toggle

## 3. 文档与校验

- [x] 3.1 更新 Image Edit、Cutout 与 Common 内部文档，说明原生对象拾取、空命中保留 source 和提交阶段有效性判断
- [x] 3.2 运行图片交互、Cutout 与 Blender Addon 定向测试并修正失败
- [x] 3.3 运行 `uv run pytest` 与 OpenSpec strict validation，不构建文档、节点资产或发布产物
