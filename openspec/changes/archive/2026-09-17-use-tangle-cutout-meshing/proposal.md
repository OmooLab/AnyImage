## Why

Cutout 在多孔区域和细长结构附近产生拉伸三角形，现有补面细分进一步增加碎面。六张透明图的实验表明，Tangle Python 版能够保留孔洞与延伸中线，效果接近已认可的 Triangle，且仅依赖 Python 标准库、采用 MIT 许可，适合随 Blender 插件分发。

## What Changes

- 使用随插件分发的 Tangle Python 实现统一构建 Cutout 基础三角网格，质量目标为 10°，密度由有效世界 Edge Length 驱动。
- Fine Outline 开启时保留精细轮廓和有效孔洞，仅过滤远小于目标尺度的微孔；关闭时填充全部封闭内部孔洞并概括外轮廓。
- 两种模式均先生成质量网格，拆分两端位于边界的内部弦，为孤立的全边界三角形补一个内部点，保持细长分支到主体的连续支撑。
- 用质量三角化替换最终建网中的旧布点与扇形补面流程，检查孔洞、实际约束链、退化面和高度结果。
- 固定第三方源码版本并保留许可；验证 Blender 实际调用与资源边界。

## Capabilities

### New Capabilities

- `cutout-quality-meshing`: 定义统一三角化、Fine Outline 孔洞策略、内部支撑与 Blender 接入验收。当前 `openspec/specs/` 为空，本变更建立此能力规格；世界边长行为承接已完成的 `use-world-space-cutout-edge-length`。

### Modified Capabilities

无已归档主规格需要修改。

## Impact

- 涉及 `src/anyimage/operators/cutout_tool/geometry.py`、统一建网模块 `mesh.py`（替换 `fine_mesh.py`）及基础网格调用链，新增第三方 Tangle 源码和 `licenses/tangle.txt`。
- 涉及 Cutout 几何、世界边长、Operator 与依赖分发相关测试。
- 运行时新增依赖为随包携带的纯 Python 源码；原有 NumPy、SciPy 继续服务于轮廓和高度计算。
- Fine Outline 的设置捕获继续覆盖同步与 AI 返回路径，基础网格供现有 Cutout Shape 使用。
