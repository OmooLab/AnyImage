# Job 产物

Server 将结果写入 Job 目录，返回以相对文件名为值的字典。Blender 主线程通过 JobResult 读取文件，创建或更新 Image、Mesh、Material 和 Object。

| Job | 文件 | 消费方 |
| --- | --- | --- |
| `remove_background` | `foreground.png` 或 `alpha.npy` | ImageEditTarget 或 HDR Alpha 编辑 |
| `upscale_image` | `upscale.png` | 图像替换 |
| `generate_depth_plane_geometry` | `depth.exr`、`depth.json` 和法线 | Depth / **浮雕** |
| `generate_cutout_artifacts` | 按请求提供深度、元数据和法线 | **立体裁切** |
| `generate_panorama_geometry` | `depth.exr`、`depth.json`、`object-normal.png` | **立体全景** |

## 深度与法线协议

| 返回字段 | 内容 |
| --- | --- |
| `depth` | float32 EXR，透视产物 RGB 保存相机空间 XYZ，Alpha 保存源 Alpha × 模型有效性 |
| `depth_metadata` | JSON，包含 `image_size` 与 3×3 `intrinsics` |
| `tangent_normal` | `tangent-normal.png`，切线空间法线 |
| `object_normal` | `object-normal.png`，对象空间法线 |

| 功能 | 法线空间 |
| --- | --- |
| 普通面片、未请求 AI 法线的裁切 | 网格法线与颜色 Bump |
| 各种带 AI 法线的裁切、凹凸面、立体全景 | Object Space |
| 浮雕 | 按平面编码的 Tangent Space |
| Bake Mesh 生成的法线贴图 | 根据最终网格与 UV 烘焙的 Tangent Space |

```mermaid
flowchart TD
    A[源 RGB 与 Alpha] --> B[限尺寸 RGB 推理]
    B --> C[GeometryFrame]
    C --> D[写出深度与法线]
    A --> E[源 Alpha 写入有效通道]
    E --> D
    D --> F[Blender 加载并 Pack]
```

参考深度由 `common/geometry_image.py` 从产物计算：先按 Alpha 阈值和有限正深度筛选样本，剔除超过样本中位数 1.1 倍的远处背景，再取 95 分位数；无可用样本时返回基准值。加载后设置 Non-Color 和 CHANNEL_PACKED。**凹凸面**使用对象空间法线，**浮雕**使用切线空间法线。

**立体全景**的 EXR RGB 保存径向距离，Alpha 保存源 Alpha 与融合有效性；元数据包含 `projection: equirectangular` 和 `image_size`。各透视视图的法线先转换至全景坐标并融合，再匹配全景网格的本地坐标编码为 `object-normal.png`。法线 PNG 均以 Non-Color 加载。

## 颜色与图像编辑

`common/color_image.py` 为**面片**、**立体全景**和**立体裁切**准备独立的材质颜色，`common/job_image.py` 从颜色文件准备 AI 分析输入。**立体裁切**使用 Selection bounds 内的源图；网格创建时组合源 Alpha 与 SelectionMask。颜色分辨率与分析尺寸分别处理。

`ImageEditTarget` 统一 Image Empty 和 Shader Image Texture 的编辑目标及共享引用。HDR 去背景通过 `HdrBackgroundInput` 保留 Blender 浮点 RGB，并应用 Server 返回的连续 Alpha。
