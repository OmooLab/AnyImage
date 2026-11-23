# 移除背景

`RemoveImageBackground` 从 Image Empty、Any Image 图片 Mesh 或当前 Shader Image Texture 读取像素，提交去背景任务，并在 Blender 中应用结果。

```mermaid
flowchart TD
    A[ImageEditTarget 取得编辑目标] --> B[准备图像输入]
    B --> C[remove_background Job]
    C --> D[所选背景模型生成前景 Alpha]
    D --> E[写出 alpha.npy]
    E --> F[确认目标仍绑定原 Image，将遮罩乘入提交时的 Alpha]
    F --> H[提交结果与 Undo]
```

`server/jobs/remove_background.py` 调用 BiRefNet 或 BEN2 生成前景遮罩。`operators/remove_background/image.py` 的 `BackgroundInput` 保留提交时的 RGBA、颜色空间和 Alpha 模式。回填时确认目标仍绑定原 Image，再合成 Alpha。HDR 结果保留浮点 RGB。Operator 负责临时输入清理与 Undo。
