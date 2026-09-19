## 1. 渐进闭合提示

- [x] 1.1 在 `common/viewport.py` 定义基于 15 px 与 UI Scale 的闭合命中半径、提示距离和 smoothstep 提示圈半径纯计算入口
- [x] 1.2 让 Polyline Overlay 在至少三个点后按鼠标距离绘制明暗双层渐进起点圈，并让点击闭合复用同一实际命中半径

## 2. 完成交互与光标

- [x] 2.1 在 Polyline Modal 中优先处理左键 `DOUBLE_CLICK`，有效路径直接完成且不追加重复顶点，点数不足时继续运行
- [x] 2.2 为统一 Mask Tool 设置 `PAINT_CROSS` cursor，并更新状态文本以说明点击起点、双击、Enter 与 Backspace 控制
- [x] 2.3 兼容 Python Modal 只收到连续 `PRESS` 的双击事件链，并复用 Blender 用户双击间隔

## 3. 验证与文档

- [x] 3.1 补充渐进提示边界、半径单调性、UI Scale、15 px 点击命中和提示范围不参与命中的测试
- [x] 3.2 补充双击有效与无效路径、无重复顶点、Mask cursor 和状态文本测试，并保持现有 Enter、Backspace 与取消测试通过
- [x] 3.3 更新 Image Edit Tool 内部文档中的 Polyline 交互说明
- [x] 3.4 运行相关交互测试与完整 `uv run pytest`，不构建文档或扩展产物
- [x] 3.5 补充连续 `PRESS` 双击的回归测试并重新运行相关测试与完整测试
