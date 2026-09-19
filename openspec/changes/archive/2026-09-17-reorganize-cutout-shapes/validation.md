# 验收记录

2026-09-07，Windows；资产构建与独立节点编辑器使用 Blender 4.5.10 LTS，Python 求值与测试使用 bpy 4.5.3。

## 自动验证

- `tools/node_assets/build.py` 完成资产重建；`validate.py`、`validate_mesh_plane.py`、`validate_cutout.py` 全部通过。
- 全量 pytest：664 passed、2 xfailed。覆盖四入口、三资产、双厚度模式、前置 Cleanup、原始深度 Split、闭合、背面平滑和法线策略。
- 测试完成后本地 bpy 运行时退出阶段发生原生崩溃（Windows 3221225477）。独立脚本调用 `pytest.main` 并将其返回码写入文件，确认返回 0；进程随后仍以访问冲突退出。测试断言均通过，进程退出问题保留为本地验证环境限制。

## 几何与视觉

- 噬菌体、蜘蛛、幼虫、心脏、棕榈树，共 15 个平滑与分离组合：非流形边、非流形顶点、零面积面均为 0，坐标有限，保留 UVMap 和 o_balloon。
- 与已接受原型逐对象比较，顶点和面数量一致；双向最近点最大位置差 0.00001258（图像尺度约 4）。
- 本机单次网格求值约 0.018–0.203 秒，包含依赖图更新与网格提取；用于观察成本，不作为性能保证。
- 背面、侧面和斜视渲染通过。Depth Solid 的 FACE 法线权重令贴图仅影响正面，背面与侧壁使用几何法线。
- 两个深度入口使用正式 O Image Layer 材质，检查两个 Inward Axis 的正背面法线方向渲染；归一化像素平均绝对差均小于 0.00000009。
- 独立隐藏 Blender 节点编辑器检查三组总览、中心场 Repeat 和闭合局部；实际绘制矩形无重叠。结构验证同时检查接口顺序、SINGLE 和未使用输出隐藏。

实验文件与详细 JSON、截图、日志位于 `build/cutout_surface_balloon/`；可编辑样例为 `cutout-production.blend`。以上验证复用缓存输入，未控制用户 Blender 实例。

## 归档衔接

`gate-cutout-ai-options`、`replace-depth-surface-stretch-with-split`、`standardize-cutout-z-axis` 后续归档时，采用本变更的四入口、三直接资产、前置 Cleanup 与原始深度 Split，保留 AI 门控和轴向约定。
