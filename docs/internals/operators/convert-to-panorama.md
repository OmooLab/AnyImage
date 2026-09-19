# Panorama 转换

`operators/convert_to_panorama/` 将静态等距柱状 Image Empty 转换为径向深度表面，提交前裁剪出最大居中 2:1 区域。`operators.py` 提交任务，`object.py` 导入对象，`__init__.py` 汇总导出与注册清单。

```mermaid
flowchart TD
    A[准备颜色与分析图] --> B[generate-panorama-geometry]
    B --> C[采样 12 个透视视图并推理]
    C --> D[融合径向距离与有效性]
    D --> E[写出 depth.exr 与 depth.json]
    E --> F[创建材质与 O Image Depth Panorama]
```

任务使用 Preferences 选择的几何模型。源颜色由 Blender 侧保存，Server 的 `geometry/panorama.py` 负责视图采样与距离融合，`jobs/panorama.py` 编排推理和产物写入。
