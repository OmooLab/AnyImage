# Operator 实现索引

| 源码（相对 `src/anyimage/`） | 功能 |
| --- | --- |
| `operators/ai_setup.py` | [AI 环境管理](ai-setup.md) |
| `operators/clipboard_image/` | [剪贴板图片](clipboard-image.md) |
| `operators/convert_to_plane/` | [Plane 与 Depth Plane](convert-to-plane.md) |
| `operators/convert_to_panorama/` | [Panorama](convert-to-panorama.md) |
| `operators/cutout_tool/` | [Cutout](cutout-tool.md) |
| `operators/frame_tool/operators.py` | [Frame 多图合成](frame.md) |
| `operators/mask_tool.py` | [Mask Alpha 编辑](mask.md) |
| `operators/rectify_tool/operators.py` | [Rectify 透视校正](rectify.md) |
| `operators/remove_background.py` | [Remove Background](remove-background.md) |
| `operators/upscale.py` | [Upscale](upscale.md) |

单文件功能按业务命名；复杂功能包在 `operators.py` 定义 Operator 和入口协调逻辑，交互式工具同时定义 WorkSpaceTool，其余模块承载具体实现。包的 `__init__.py` 汇总导出与 `CLASSES` 注册清单，类型在 `operators/__init__.py` 和扩展 `__init__.py` 汇总注册。AI Operator 使用普通字典提交任务，并在主线程响应中读取文件和修改 Blender 数据。
