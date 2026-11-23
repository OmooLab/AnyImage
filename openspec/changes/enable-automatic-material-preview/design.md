## Context

本地 Cutout 与 AI Cutout 共用 `create_cutout_shape`。Convert to World 在 `execute` 中同步设置 World，Convert to Panorama 在 `response` 中应用结果。BlendJob 调用 `response` 前已恢复提交任务时的窗口、区域和 region。

## Goals / Non-Goals

用户用一个偏好开关控制三个操作。每次只调整发起操作的 3D 视图，允许写入的属性限于着色模式，以及两个环境转换使用的 Scene World。

## Decisions

- 在 `preferences.py` 的 `PreferencesLite` 中声明 `auto_material_preview`，默认值为 `True`，在共用 Tools 区显示。完整版的 `Preferences` 已继承这个类并调用其绘制方法。
- 在 `common/viewport.py` 增加一个函数 `apply_material_preview(context, *, use_scene_world=False)`。通过 `addon_preferences(context)` 读取开关，只处理传入的 `context.space_data` 为 `VIEW_3D` 的情况。这样同步操作与 AI 回调可用同一段逻辑，也无需缓存视图引用或遍历窗口。
- 在 `create_cutout_shape` 准备好输入、调用 `create_shape_object` 前调用该函数。画选区和等待 AI 时仍可自由调整视图，函数以实际创建时的模式为准。
- Convert to World 在转换成功、返回前调用；Convert to Panorama 在成功应用结果的回调末尾调用。两处均传入 `use_scene_world=True`。

| 调用时的模式 | 最终模式 | Cutout | World / Panorama |
| --- | --- | --- | --- |
| `SOLID` 或 `WIREFRAME` | `MATERIAL` | 只切换模式 | 勾选 `use_scene_world` |
| `MATERIAL` | `MATERIAL` | 保留视图设置 | 勾选 `use_scene_world` |
| `RENDERED` | `RENDERED` | 保留视图设置 | 勾选 `use_scene_world_render` |

## Risks / Trade-offs

Material Preview 和 Rendered 分别保存 Scene World。按最终模式选择对应属性，可保留另一模式的选项以及 Scene Lights、工作室灯光等独立设置。
