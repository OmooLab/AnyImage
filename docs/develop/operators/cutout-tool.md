# 立体裁切

**立体裁切**在静态 Image Empty 上圈定 Selection，按轮廓创建**平面**、**实体**、**深度对称**或**深度实体**。Operator 入口位于 `operators/cutout_tool/operators.py`，WorkspaceTool 声明位于 `tools.py`，Shape 菜单位于 `interaction.py`，预设标识与节点组对应关系位于 `shape.py`。

```mermaid
flowchart TD
    A[套索或折线提交 SelectionPath] --> B[选择 Shape]
    B --> C[栅格化 SelectionMask 并读取源 RGBA]
    C --> D{需要 Depth 或 Normal？}
    D -- 是 --> E[准备 bounds 矩形 RGBA]
    E --> F[generate-cutout-artifacts]
    F --> G[加载 Depth、Metadata 与 Normal]
    D -- 否 --> H[源 Alpha 与 SelectionMask 组合]
    G --> H
    H --> I[边界映射、轮廓提取与质量三角化]
    I --> J[BaseShape 与 o_balloon]
    J --> K[创建材质、对象与对应节点修改器]
```

| 预设 | 节点组 | AI 产物 |
| --- | --- | --- |
| **平面** | `O Image Cutout`，Thickness 0 | 可选切线空间法线 |
| **实体** | `O Image Cutout`，Thickness 1 | 可选切线空间法线 |
| **深度对称** | `O Image Depth Cutout` 与 `O Image Cutout Symmetry` | 深度与对象空间法线 |
| **深度实体** | `O Image Depth Cutout` | 深度与对象空间法线 |

**平面**与**实体**可以不带 AI 产物生成；Depth 预设和**法线贴图**需要就绪的几何模型，Shape 菜单按该状态提供选项。

## 轮廓与网格

`geometry.py` 从内容 Alpha 提取连通轮廓与孔洞，按**边长**生成 `BaseShape`。**边长**是世界空间的网格目标边长，**最小相对边长**会按内容范围提高其下界。

`mesh.py` 负责轮廓分离、孔洞处理、质量三角化和边界支撑，`polygon.py` 提供轮廓简化，`tangle.py` 是随包分发的 Delaunay 三角化核心。**精细轮廓**展开时保留小孔与细节轮廓，关闭时填洞并简化。

`balloon.py` 负责 **鼓起形状**，按 Preferences 选择 Poisson 或 Teddy，生成所有预设共用的 POINT 属性 `o_balloon`。`boundary_padding.py` 按**边界扩展**沿结构内法线重采样轮廓附近的颜色与深度。

## AI 与对象创建

Server 接收 Selection bounds 内保留源 Alpha 的 RGBA，一次 MoGe 推理按 `generate_depth` 与 `normal_mode` 返回产物。深度参考区域使用所选**透明度阈值**，Normal 使用原预测；**AI 输入尺寸上限**只影响分析分辨率。

`object.py` 的 `create_shape_object()` 消费 BaseShape、Color、Depth 和 Normal，加载对应节点组。基础网格位于局部 XZ 平面，厚度沿 Y 展开；对象矩阵把网格放入 Image Empty 的图片平面，**深度对称**额外叠加对称节点组与方向参数。Object Normal 随方向同步转换。

材质使用 IOR 1.2，颜色与法线接入 Image Layer，法线按切线或对象空间解释。节点计算见[节点资产](../node-assets.md)。
