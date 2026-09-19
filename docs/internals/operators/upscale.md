# Upscale

`operators/upscale.py` 从 Image Empty 或当前 Shader Image Texture 生成 2× 结果，源图长边必须小于 Maximum AI Input Size。

```mermaid
flowchart TD
    A[检查源图尺寸并冻结模型设置] --> B[准备图片输入]
    B --> C[upscale-image 单张处理]
    C --> D[分块执行 4× RGB 推理]
    D --> E[统一缩放为源图 2×]
    E --> F[原 Alpha 独立 Lanczos 缩放]
    F --> G[ImageEditTarget 应用结果并提交 Undo]
```

`server/models/upscale.py` 处理输入上限和最终尺寸，`onnx_upscale.py` 执行 Real-ESRGAN 与 HAT 模型。ModelManager 管理 Session；Provider 资源错误会释放当前 Session 并返回处理建议。
