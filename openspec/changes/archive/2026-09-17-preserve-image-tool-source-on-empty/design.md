## Context

图片工具没有实现自定义 Viewport Picker。普通点击由 keymap 调用 Blender `view3d.select`；Mask 与 Rectify 因为以 `PRESS` 启动 Operator，由 `resolve_image_edit_click()` 主动调用同一个原生选择。AnyImage 只比较点击前后的 active object，并验证 active source 是已选择的 Image Empty。

当前两条入口都把 `deselect_all=True` 传给原生选择。Image Empty 的透明像素可能没有拾取结果，因此透明区域与 Viewport 空白都会清除 active source。Mask、Rectify 和 Cutout 随后的起始动作便依赖第一点命中非透明图片内容。

## Goals / Non-Goals

**Goals:**

- 让 Mask、Rectify 与 Cutout 在已有 active Image Empty 时从透明区域或 Viewport 空白开始操作。
- 继续使用 Blender 原生 Picker 决定命中的对象、active object 和普通选择结果。
- 保持点击另一对象只切换选择、不同时启动图片操作。
- 将行为变化限制在三个绘制型工具，不改变 Frame 的多选工作流。

**Non-Goals:**

- 不实现只允许 Image Empty 的自定义 Picker、射线检测或 Alpha 命中。
- 不撤销或过滤 Mesh、Light 等非 Image Empty 的原生选择结果。
- 不保存隐藏的图片目标，也不在工具激活时冻结 source object。
- 不改变手势投影、图片范围裁切、可见内容判断或结果生成。

## Decisions

### 1. 原生 Picker 使用不清空选择的空命中策略

`resolve_image_edit_click()` 继续调用 `bpy.ops.view3d.select`，但使用 `deselect_all=False`。命中另一对象时 Blender 正常更新 active，函数返回该对象并结束本次 Operator；没有命中时 active 保持为原 Image Empty，函数把同一次事件解释为图片操作起点。

相比先执行默认选择再保存和恢复 Selection，这一方式不需要手动复制多选集合、写入 `select_set()` 或重建 active object。相比自定义射线检测，它继续继承 Blender 对遮挡、对象可选状态和 Viewport 的完整规则。

### 2. Cutout 单击使用同一空命中策略，Frame 保持原行为

Cutout 的 Lasso 由 `CLICK_DRAG` 启动，普通 `CLICK` 仍交给原生对象选择。公共 selection keymap 提供明确的 `deselect_on_empty` 策略：Cutout 传入 false，使空白单击保留 active source；Frame 沿用 true，使其多选图片集合仍可通过空白点击清空。

Mask 与 Rectify 的普通按下事件由 Operator 接管，空命中策略由 `resolve_image_edit_click()` 负责。Cutout 的整图双击也复用该解析入口。Shift 点击继续使用现有原生 toggle，不增加过滤规则。

不选择全局修改公共 keymap 默认值，因为 Frame 与三个单图片绘制工具的选择目的不同。

### 3. Source eligibility 与对象选择保持分离

命中任何另一对象时都保留 Blender 的选择结果，无论它是否为 Image Empty，本次不启动编辑。下一次操作仍通过 `active_image_edit_source()` 要求 active object 是已选择的 Image Empty；条件不满足时报告现有 warning。

不自动取消非 Image Empty，因为这会把 AnyImage 从业务资格验证扩展成对象选择管理，并使用户无法按 Blender 预期选择其他场景对象。

### 4. 起始点不判断图片范围或 Alpha

没有拾取结果只表示继续使用 active source，不表示起点已经落在图片内容内。Mask、Rectify 与 Cutout 继续把完整手势投影到图片平面，并在提交阶段执行既有的画布相交、Alpha 内容和有效几何检查。完全位于图片外的手势仍取消并报告对应 warning。

## Risks / Trade-offs

- [工具激活时空白点击不再 deselect all] → 这是三个绘制型工具维持操作对象的明确语义；用户仍可使用 Blender 的取消选择命令，Frame 也保留原行为。
- [点击非 Image Empty 会失去当前图片 active] → 保留原生选择结果比维护隐藏 source 更可预测；用户重新点击目标 Image Empty 后即可继续。
- [透明区域与真正的 Viewport 空白无法区分] → 两者都作为当前图片平面上的合法起始坐标处理，最终范围检查统一决定是否执行。
- [共享 keymap 的参数可能意外改变 Frame] → 测试分别固定 Cutout 的 false 与 Frame 的 true，并保持默认值表达 Frame 现状。

## Migration Plan

1. 为公共 selection keymap 增加空命中策略，并仅在 Cutout 选择入口关闭 deselect all。
2. 修改点击解析入口，使 Mask、Rectify 和 Cutout 双击在空命中时保留 active source。
3. 更新交互测试和当前内部文档，运行定向测试与完整测试。

回退时恢复两个原生选择调用的 `deselect_all=True`；不涉及持久数据、对象结构、Operator 参数或兼容层。

## Open Questions

无。
