# 转为面片、转为凹凸面与转为浮雕

普通面片入口位于 `operators/convert_to_plane.py`。`operators/depth_plane/operators.py` 为凹凸面与浮雕提交整图的 sRGB PNG，`object.py` 在结果返回后从原图创建材质，并用深度与法线创建对象。三种面片共用 `common/image_plane.py` 的基础矩形网格。

```mermaid
flowchart TD
    source["整张原图"] --> type{"转换类型"}
    type -->|面片| material["从原图创建材质"]
    type -->|凹凸面或浮雕| ai["sRGB PNG → AI 深度与法线"]
    ai --> checked["校验原图"]
    checked --> material
    material --> result["创建面片和对应的节点修改器"]
```

三种转换都只接受静态图片。基础网格以局部中心为原点，对象矩阵补偿源 Empty 的显示范围。

Depth 与 Relief 从 Preferences 读取几何模型、分辨率级别和 AI 输入上限。`create_depth_plane_from_result()` 导入产物并创建修改器。排队时保留源 Object 和 Image 的原生引用，回填时校验其绑定与图像内容摘要，重命名保持任务有效，等待期间换图或修改像素、尺寸、颜色解释会拒绝回填。`O Depth Plane` 使用相机 XYZ 与对象空间法线构建深度表面；`O Depth Relief` 使用深度 Z 与切线空间法线构建浮雕。

节点构建见[节点资产](../node-assets.md)，文件协议见[Job 产物](../outputs.md)。
