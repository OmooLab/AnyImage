## 1. 数值依赖与深度修复

- [x] 1.1 确定兼容开发和服务端 Python、NumPy 的 SciPy 版本，同步 `runtime.py`、`pyproject.toml` 和 `uv.lock`，检查 Manifest 与环境、打包测试约束。
- [x] 1.2 在 `server/geometry/edge_depth.py` 实现连续 Alpha 对齐、可靠候选、2 px 欧氏内缩及图片边缘延续，补充阈值和贴边主体测试。
- [x] 1.3 实现按可见域 8 连通分量选取最近供体，以及无内缩核心、无候选的回退规则，测试细小分量与不同深度的相邻分量。
- [x] 1.4 实现透明区 4 px 外扩和 σ=0.8 px、半径 3 px 的局部平滑，测试核心逐值不变、邻域采样与跨分量隔离。

## 2. 产物接入

- [x] 2.1 按 Frame 内参和当前像素射线重建修复区域 XYZ；复用现有服务端反投影能力，测试非方形图片、像素中心、有限值及小于 1e-6 的归一化投影误差。
- [x] 2.2 为 `generate_moge2_artifacts()` 增加内部修复选项，由 Cutout Job 在深度请求中启用；Vector/Z Depth 与 Metadata 共用修复后 Frame，保留模型 Validity 和原始 Normal Writer 输入。
- [x] 2.3 补充任务回归测试，覆盖 Depth Surface、Depth Balloon、完全不透明图片、普通 Depth Plane 和仅 Normal 请求的产物行为。

## 3. 验证

- [x] 3.1 运行数值、服务端任务、运行环境和打包相关测试，再运行 `uv run pytest`。
- [x] 3.2 用可重建的 2048 长边输入检查处理时间、峰值内存和分量数量对开销的影响，确认局部范围处理可用。
- [x] 3.3 使用两张用户原图重新执行 BEN2 与 MoGe，固定同一 Alpha 和预测，对比修复前后边缘跳变、可见域及正面投影；补充缩放输入检查，记录结果。
- [x] 3.4 使用现有 Blender 节点资产验收两张图的 Depth Surface、Depth Balloon 和 Normal 开关组合，检查线性采样、平滑、厚度与拉伸剔除后的侧视拖尾及残余台阶、着色问题。

## 验证记录

- `uv run pytest -q`：524 passed，56 subtests passed。
- SciPy 1.15.3 支持 Python ≥ 3.10、NumPy ≥ 1.23.5 且 < 2.5；已在开发和服务端环境执行。
- 2048×2048、1/64/1024 个分量：0.445/0.399/0.394 秒；独立进程峰值工作集约 453/343/367 MiB（处理前约 229 MiB）。
- 猫与人物原图及半尺寸图完成重新推理，正面投影误差均小于 3×10⁻⁸，可靠核心逐值保持。猫原图边缘跳变 P95 从约 14.86% 降至 0.10%，人物从约 2.98% 降至 0.35%（以各自参考深度归一化）。
- Blender 4.5.3 现有资产完成 16 组渲染，并对平滑 2 次、厚度 0.02、Stretch Limit 0.05 组合额外求值；所有网格坐标有限。Depth Surface 主要拖尾消除，猫最大网格边长从 2.266 降至 0.107，人物从 1.311 降至 0.662。Depth Balloon 轮廓整体稳定，人物手部原有拉伸仍可见；原始 Normal 的边缘着色仍有局部差异。
- 本地验证脚本、预测、指标及渲染位于 `C:/Users/icrdr/.codex/visualizations/2026/09/05/01a071bc-9eae-7f91-8791-816aa621fd8a/verification/`；脚本 `verify_edge_depth.py`、`verify_blender_depth.py` 位于其父目录。
