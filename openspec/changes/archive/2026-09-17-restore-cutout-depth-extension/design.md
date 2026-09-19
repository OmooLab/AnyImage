## Context

共享 MoGe 产物入口当前直接输出预测 XYZ。本变更在 Cutout 深度产物写入前加入边缘延伸，生成的贴图由现有几何节点直接消费。

独立实验位于 `C:/Users/icrdr/.codex/visualizations/2026/09/13/cutout-depth-4px/`，`report.md`、脚本、预测、对照图及 Blender 文件记录完整过程。使用 v26 节点组、BiRefNet Lite、MoGe-2 ViT-S Level 5，同一 Alpha 和预测，剪裁阈值 0.9，世界边长 0.015，Depth Split=0.1。蜘蛛/头骨补边约 35/26 ms，拖尾明显减少，细腿仍有断裂与折点。该节点版本仅是已有实验条件；实施验收使用现有节点和固定参数，仅替换深度产物。

## Goals

以一次深度补边稳定 Cutout 轮廓采样，保持可靠内部、相机投影和产物有效性一致。

## Decisions

### 沿用实测的固定来源规则

恢复 `31074bd^:src/anyimage/server/geometry/edge_depth.py` 的算法语义。剪裁阈值用于可见域及其 8 连通分量；可靠候选在该分量内满足 Alpha ≥ 0.95、Validity > 0.5、深度有限且为正。0.95 是固定来源条件，不新增随剪裁阈值变化的参数逻辑。低剪裁阈值可以保留毛发，但低 Alpha 像素仍从可靠来源取得深度。

不透明候选域按图片边缘延续计算距离，距离域外大于 2 个深度图像素的可靠候选作为供体。没有核心时回退到本分量未内缩的可靠候选；仍无候选则保留原预测。保持旧算法对内部区域的保护：模型 validity 孔洞只影响来源资格。

每个分量以最近供体 Z 延伸到边缘及可见域外 4 px。使用 sigma=0.8、半径3 px的 Gaussian，仅写回旧算法定义的补齐区；分量局部 padding 为7 px，重叠透明区域由最近可修复分量提供。完整不透明输入原样返回。

### 在 Cutout 产物边界启用

共享 `generate_moge_artifacts()` 接收默认关闭的内部补边选项，由 `server/jobs/cutout.py` 在请求深度时开启。模型只推理一次，保留原始 Frame，另取修复 Frame 写入 Cutout EXR 和 Metadata。Normal Writer 消费原始 Frame；Depth Plane 等调用保持默认行为。

修改 Z 后使用当前像素中心射线重建 XYZ，复用服务端已有反投影函数并处理像素/归一化内参。仅写回变化像素，保留原 validity；EXR A 继续为原图 Alpha × 原 validity，Metadata 参考深度按修复 Frame 和原参考掩码计算。复用已声明的 NumPy/SciPy，实施时核对独立服务端依赖。

## Risks / Trade-offs

- 固定宽度对低分辨率、细腿覆盖比例较大 → 验证细分量回退及两张实图；维持已实测参数。
- 高 Alpha 仍可能包含错误深度 → 保留内侧保护带；实图报告残余断裂和内部深度错误。
- 补边有一次生成成本 → 分别记录补边耗时与后续节点求值耗时。
- Normal 来自原始预测 → 对修复边缘检查材质着色，明确几何与法线差异。

## Migration Plan

实施调整服务端深度处理与 Cutout 产物调用。新生成 Cutout 获得修复深度，已有对象可通过重新生成取得新产物。几何节点保持当前逻辑、参数和资产；相关测试与工作区外实图验收通过后交付。
