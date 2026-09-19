## Context

当前图片选区业务横跨 Blender 侧数据结构、Viewport 手势、Image Tool、Cutout Tool 和 Server Job，但统一使用 `region`；与此同时 Blender API 也用 Region 表示编辑器窗口区域。两种含义出现在同一调用链中，增加了阅读和查找成本。

当前工作树已将 Blender 侧共享模块整理为 `common/region.py` 与 `common/viewport.py`。本次变更以该结构为迁移起点，并遵守项目不保留旧入口或兼容层的约束。Server 仍保持独立包边界，不能引用上级共享模块。

## Goals / Non-Goals

**Goals:**

- 让图片选区从数据类型到 Job 产物全程只使用 `selection`。
- 明确区分图片 Selection 与 Blender Viewport Region。
- 用面向用户的 Mesh Detail 代替实现导向的像素采样间距。
- 一次性迁移所有内部调用方、测试和文档，不留下混合术语。

**Non-Goals:**

- 不修改路径栅格化、Mask 运算、BEN2 细化或 Normal Map 生成算法。
- 不增加新的网格采样密度，也不改变四个既有间距的几何结果。
- 不重命名 Blender API 规定的 Region 概念，也不替换与图片选区无关的普通区域表达。
- 不改变 AI 可用性门控、Shape 候选项或 Normal Space 规则。

## Decisions

### 1. 按业务含义迁移，不做全局文本替换

业务选区主链统一采用以下名词：

| 当前表达 | 目标表达 |
| --- | --- |
| `common/region.py` | `common/selection.py` |
| `RegionPath` / `RegionMask` / `RegionContours` | `SelectionPath` / `SelectionMask` / `SelectionContours` |
| `region_path` / `region_mask` / `region_contours` | `selection_path` / `selection_mask` / `selection_contours` |
| `ImageRegionGesture` | `ImageSelectionGesture` |
| `SelectCutoutRegion` / `CutoutRegionToShape` | `SelectCutoutSelection` / `CutoutSelectionToShape` |
| `RefineImageRegion` / `refine-image-region` | `RefineImageSelection` / `refine-image-selection` |
| `refine_region` | `refine_selection` |
| `region_image` / `region_bounds` | `selection_image` / `selection_bounds` |
| `server/region/refine_region.py` | `server/selection/refine_selection.py` |

同一规则应用于相关函数、属性、序列化字段、进度消息、临时文件和测试名称。由于项目不保留兼容层，旧模块、Operator ID、Job 类型和字段在迁移完成后直接删除。

不纳入迁移的名称包括 `context.region`、`context.region_data`、`event.mouse_region_x/y`、Viewport Region 指针与尺寸，以及算法中确实表示一般连通区域而非用户 Selection 的术语。相比机械替换，按语义清单迁移可以避免破坏 Blender API，并使残留检查具有明确判断标准。

### 2. Selection 是业务名词，Refine 是动作

属性工厂和三个工具设置分别改为 `refine_selection_property`、`cutout_refine_selection`、`image_box_refine_selection` 与 `image_lasso_refine_selection`，Operator 参数使用 `refine_selection`。界面统一显示 **Refine Selection**，描述说明使用 BEN2 将手势产生的 Selection 收紧到前景。

相较只改界面文案，此方案让代码与界面保持同一概念；相较继续使用 `fit`，`refine` 更准确地表达已有 AI 操作，并与原名称一致。

### 3. Normal Map 只缩短用户界面名称

Cutout 布尔选项显示名从 **Generate Normal Map** 改为 **Normal Map**。`generate_normal` 等执行层标识继续表达“是否生成”这一布尔动作，不为追求表面一致而改成含义更弱的 `normal_map`。

### 4. Mesh Detail 映射到既有采样间距

Cutout 设置从 `cutout_point_spacing` 整数属性迁移为 `cutout_mesh_detail` 枚举属性，显示名为 **Mesh Detail**。枚举标识使用稳定字符串 `"LOW"`、`"MEDIUM"`、`"HIGH"`、`"ULTRA"`，使代码标识与界面档位直接对应；创建 Shape 前通过单一映射转换为实际采样间距：

| Mesh Detail | Sampling Spacing |
| --- | --- |
| Low | 32 px |
| Medium | 16 px |
| High | 8 px |
| Ultra | 4 px |

默认值为 Low，与当前默认 32 px 保持一致。转换函数放在使用网格间距的 Cutout 业务边界，后续几何代码仍接收明确的像素间距，不让 UI 档位渗入采样算法。

相比保留 4–32 的任意整数输入，四档枚举只暴露实际支持和测试的密度；相比直接把 Level 数值传入几何代码，显式映射保留了算法参数的物理含义。

### 5. Server 协议与文件产物同步切换

Blender 和 Server 在同一次变更中切换 Job 类型、参数、结果字段及产物文件名。建议的细化产物为 `selection.png` 与 `selection_bounds.json`；独立 Image Selection Job 的通用输出仍可沿用 `image.png` 与 `bounds.json`，但结果字典键使用 `selection_image` 与 `selection_bounds`。

协议不做双读或双写。这样符合项目移除旧路径的规则，也避免长期维护两套字段；代价是旧会话中尚未完成的 Job 结果不能由新代码恢复。

## Risks / Trade-offs

- [遗漏某个业务 `region` 导致混合术语或运行时字段不匹配] → 按模块清单迁移，并用定向 `rg` 结合人工语义复核；测试覆盖 Blender 调用与 Server 返回值两端。
- [机械重命名误伤 Blender Viewport Region] → 将 Blender API 名称列入明确保留清单，重点运行手势绘制、投影和 Perspective 相关测试。
- [与当前 `reorganize-common-modules` 工作树重叠] → 以其整理后的 `common/selection.py` 目标结构为准，不恢复已删除的旧模块。
- [旧 `.blend` 中保存的工具设置名失效] → 接受该迁移成本，不增加兼容属性；工具设置回到新属性的默认值。
- [Mesh Detail 顺序与采样间距方向写反] → 使用单一常量映射，并对 Low、Medium、High、Ultra 四档添加参数化测试。
- [旧 Job 或临时结果不可恢复] → 同版本同步发布 Blender 与 Server 代码，并接受更新时终止中的旧 Job。

## Migration Plan

1. 先迁移 Selection 数据模块、类型和纯函数，再更新 Blender 侧所有导入与调用。
2. 迁移 Viewport 手势、工具属性和 Operator，同时切换 Mesh Detail 枚举与间距映射，更新注册与逆序注销。
3. 同步迁移 Server 包、Job 类型、参数、结果字段和产物文件名。
4. 更新测试与内部文档，使用搜索确认剩余 `region` 均属于保留语义。
5. 运行相关测试后运行全部测试；若失败，整体回退本次重命名，不引入临时兼容层。
