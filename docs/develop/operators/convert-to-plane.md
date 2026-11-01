# 转为面片、转为凹凸面与转为浮雕

三个转换入口分别位于 `operators/convert_to_plane.py`、`convert_to_depth_plane.py` 与 `convert_to_relief.py`。各入口声明自己的 Operator；`common/image_plane.py` 创建基础矩形网格与面片，`common/depth_plane.py` 复用深度产物导入和对象创建。凹凸面与浮雕指定各自的固定类型，由 `operators/plane_geometry.py` 统一准备输入快照，并通过内部 `GeneratePlaneGeometry` 提交几何 Job。

```mermaid
flowchart TD
    A[Image Empty] --> B[准备材质颜色]
    B --> C{转换类型}
    C -- 面片 --> D[四边形与 O Plane]
    C -- Depth 或 Relief --> E[静态图提交几何 Job]
    E --> F[加载深度、元数据与法线]
    F --> G[对应节点修改器与材质]
    D --> H[创建对象并替换源 Empty]
    G --> H
```

三种转换都只接受静态图片。基础网格以局部中心为原点，对象矩阵补偿源 Empty 的显示范围。

Depth 与 Relief 从 Preferences 读取几何模型、分辨率级别和 AI 输入上限。`create_depth_plane_from_result()` 导入产物并创建修改器。排队时保留源 Object 和 Image 的原生引用，回填时校验其绑定与图像内容摘要，重命名保持任务有效，等待期间换图或修改像素、尺寸、颜色解释会拒绝回填。`O Depth Plane` 使用相机 XYZ 与对象空间法线构建深度表面；`O Depth Relief` 使用深度 Z 与切线空间法线构建浮雕。

节点构建见[节点资产](../node-assets.md)，文件协议见[Job 产物](../outputs.md)。
