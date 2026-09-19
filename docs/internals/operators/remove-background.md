# Remove Background

`operators/remove_background.py` 从 Image Empty 或当前 Shader Image Texture 准备输入。`RemoveImageBackground` 协调设置与输入，`RunBackgroundRemoval` 提交 Job 并应用结果。

```mermaid
flowchart TD
    A[ImageEditTarget 取得编辑目标] --> B[准备图像输入]
    B --> C[remove-background Job]
    C --> D[所选背景模型生成前景 Alpha]
    D --> E{输入类型}
    E -- 普通图片 --> F[透明 PNG 前景]
    E -- HDR --> G[alpha.npy]
    F --> H[应用结果与 Undo]
    G --> H
```

`server/jobs/remove_background.py` 读取单张输入并调用 `server/models/background.py`，支持 BiRefNet 和 BEN2。模型前景 Alpha 与源 Alpha 合成。

普通结果通过 `ImageEditTarget` 保留共享图像引用与帧设置。HDR 使用 `common/hdr_image.py` 的 `HdrBackgroundInput` 准备分析输入，并将返回 Alpha 应用于原浮点 RGB。Operator 负责临时输入清理。
