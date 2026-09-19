## Why

Cutout 轮廓附近的背景深度会形成长条拖尾。蜘蛛和恐龙头骨实测表明，生成时延伸深度 4 像素可明显减少拖尾，适合在深度产物生成阶段恢复。

## What Changes

- 仅为 Cutout 深度产物恢复已实测的旧版边缘延伸：可靠来源 Alpha ≥ 0.95、内侧保护 2 px、外侧延伸 4 px、局部平滑。
- 保留旧算法的来源筛选、分量隔离与回退规则；剪裁 Alpha 继续定义可见轮廓，不新增来源阈值联动或设置。
- 普通 Depth Plane、全景深度与 Normal 使用原始预测；Cutout 深度及 Metadata 使用同一修复结果。

## Capabilities

### New Capabilities

- `cutout-depth-extension`: Cutout 专用的可靠边缘深度延伸、产物隔离与实图验收。

### Modified Capabilities

无；相关规范尚未归档至 `openspec/specs`。

## Impact

涉及 Cutout Job、共享 MoGe 产物入口、服务端深度处理与相关测试。复用现有 NumPy/SciPy，核对服务端依赖声明。实现范围为生成的 Cutout 深度图及配套 Metadata；几何节点源码、参数、revision 和 `.blend` 资产保持现状。
