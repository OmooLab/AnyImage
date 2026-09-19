## Why

Cutout 在低密度下轮廓偏离原图，细腿缺少连续内部顶点时 Balloon 会形成扁平断点。实验还发现，高密度只细分简化直边无法提高贴合度；轮廓精度、内部连通性和计算开销需要一起约束。

## What Changes

- 新增默认开启的 Fine Outline（精细轮廓）。开启使用自适应网格；关闭保留原轮廓平滑、概括和均匀布点算法，适合蕨叶等密集细部。
- 设置保存在 Scene，打开 Shape 菜单时捕获到 Operator，覆盖本地及 AI 返回后的创建流程。
- Mesh Detail 同时控制轮廓近似误差和内部目标间距；Low 保留概括，High、Ultra 从源轮廓恢复更精细的形状。
- 为保留的细长结构构建稀疏、连续的内部约束路径，并在最终网格和 Balloon 高度中验证路径完整性。
- 固定轮廓与结构路径，均匀化其余内部点；通过局部细分处理边缘与内部的尺寸过渡。
- 在网格生成前过滤极小独立区域，保留最大区域和与主体相连的细腿。
- 批量复用边界几何检查，合并路径搜索，限制均匀化采样量并按收敛停止；每次创建依据输入重新准备结构。
- 增加轮廓误差、跨密度连通性、拓扑质量和首次生成耗时的回归验收。

## Capabilities

### New Capabilities

- `cutout-adaptive-mesh`: Cutout 的轮廓精度、稀疏内部支撑、约束网格、碎片清理和性能验收。

### Modified Capabilities

## Impact

- `src/anyimage/operators/cutout_tool/geometry.py` 及 Cutout 几何模块：根据 Fine Outline 选择平面网格算法，复用现有高度求解能力。
- `src/anyimage/operators/cutout_tool/main.py`、`object.py`：核对各 Shape 的几何输入、像素坐标和高度消费边界。
- `tests/test_cutout_geometry.py` 及独立性能实验：补充真实问题的合成回归样本和四档密度检查。
- 客户端数值依赖与打包检查：实验使用 NumPy、SciPy、scikit-image 和 Blender CDT；正式实现需验证 Blender Python 中的可用性与平台 wheel 支持。
- 沿用 Low / Medium / High / Ultra 的 32 / 16 / 8 / 4 源像素目标间距和现有网格分辨率上限。
