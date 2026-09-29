## Why

Cutout 在创建阶段建立双区图片，使基础 UV、Depth 采样、侧壁构造和图片处理提前依赖最终纹理布局。将独立纹理区域的生成集中到 Convert to Mesh，可以让可编辑对象保持单图协议，并在转换时同时固化正背面、symmetry 与法线效果。

## What Changes

- **BREAKING**：可编辑 Cutout 的 Color、Normal 使用单区图片和完整 0–1 UV；彻底删除创建阶段的旧双区拼接、上半区初始化、下半区变换和 Atlas 专用 Depth 还原代码及旧测试。
- 增加 AnyImage `Convert to Mesh`，将当前 Cutout 求值结果原位转换为静态 Mesh；转换阶段按实际表面来源生成独立纹理区域，支持厚度和一次 symmetry 组合产生的 1、2、4 个主要区域。
- 将当前法线旋转、镜像、正背处理、Normal Scale、空间变化的衰减及补面禁用效果固化成最终 UV 下的静态 Tangent Normal；转换结果不再依赖法线属性。
- 转换成功后清除 AnyImage 的形状、区域、法线及中间数据属性和程序化对象标记；保留 UV、必要的 Blender 网格数据及用户自有数据。
- 保留材质结构及共享 `O Image Layer`，仅隔离共享材质、更新图片及必要输入；静态结果使用 Tangent 模式和单位 Normal Scale。
- 完整替代尚未归档的 `split-cutout-front-back-uv` 的双区协议，不保留旧路径、开关或转发层。

## Capabilities

### New Capabilities

- `cutout-texture-materialization`: 单图编辑阶段、静态 Mesh 转换、纹理区域布局、法线固化、事务提交与旧拼接路径清理。

### Modified Capabilities

- `cutout-attribute-lifecycle`: 明确可编辑节点输出与静态转换结果的属性生命周期；静态结果清除全部 AnyImage 协议数据。
- `material-color-images`: 创建 Cutout 时使用单区裁切内容，独立区域由静态转换生成。
- `cutout-double-sided-textures`、`depth-artifact-contract`、`cutout-shape-presets`: 提供前置变更 `split-cutout-front-back-uv` 归档后的移除 delta，废止其创建期双区要求；本变更在它之后归档。

## Impact

- 涉及 `src/anyimage/operators/cutout_tool`、新增转换 Operator、材质及图片共用函数、菜单和注册入口，以及 `nodes/common/cutout.py`、Cutout、Depth Cutout 和 Symmetry 节点源码。
- 涉及相关图片、节点求值、法线渲染、Undo / Redo、共享数据隔离和注册测试；节点修改后运行 `uv run --group blender node-group build`。
- 优先使用现有 Blender 与 NumPy 能力。共享 `O Image Layer` 的实时法线能力继续服务于可编辑对象；转换结果通过 Tangent 路径读取静态图。
- 实施更新相关测试和 OpenSpec，不主动同步说明文档、构建文档或打包扩展。
