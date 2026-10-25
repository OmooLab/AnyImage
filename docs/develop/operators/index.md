# Operator 实现索引

| 源码（相对 `src/anyimage/`） | 功能 |
| --- | --- |
| `operators/ai_setup.py` | [AI 环境管理](ai-setup.md) |
| `operators/clipboard_image/` | [剪贴板图片](clipboard-image.md) |
| `operators/convert_to_plane/` | [**转为面片**、**转为凹凸面**与**转为浮雕**](convert-to-plane.md) |
| `operators/convert_to_panorama/` | [**转为立体全景**](convert-to-panorama.md) |
| `operators/cutout_tool/` | [**立体裁切**](cutout-tool.md) |
| `operators/frame_tool/operators.py` | [**重设画框**](frame.md) |
| `operators/mask_tool.py` | [**局部显隐** Alpha 编辑](mask.md) |
| `operators/rectify_tool/operators.py` | [**透视校正**](rectify.md) |
| `operators/remove_background/operators.py` | [**移除背景**](remove-background.md) |
| `operators/color_match.py` | [**色彩匹配**](color-match.md) |
| `operators/bake_mesh/operators.py` | [**烘焙网格**](bake-mesh.md) |
| `operators/job_files.py` | [Job 文件清理](job-files.md) |
| `operators/upscale.py` | [**2倍高清**](upscale.md) |

单文件功能按业务命名；复杂功能包在 `operators.py` 定义 Operator 和入口协调逻辑，其余模块承载具体实现。包的 `__init__.py` 汇总导出与 `CLASSES` 注册清单，类型在 `operators/__init__.py` 和扩展 `__init__.py` 汇总注册。交互式工具的 WorkspaceTool 统一定义和注册于 `tools.py`。AI Operator 使用普通字典提交任务，并在主线程响应中读取文件和修改 Blender 数据。
