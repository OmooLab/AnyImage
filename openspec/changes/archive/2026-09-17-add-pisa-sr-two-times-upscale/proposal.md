## Why

现有 Upscale 每次把宽高放大 4 倍，尺寸增长过快。PiSA-SR 在已测试的 0.7 细节强度下能够补充更丰富的纹理，适合作为新的生成型选项；所有模型统一每次输出 2×，方便逐步放大。

## What Changes

- 新增 `PiSA-SR` 模型选项，固定 `lambda_pix=1.0`、`lambda_sem=0.7`，输出宽高各为输入的 2 倍。
- **BREAKING**：现有 General WDN x4v3、SAFMN Real x4、Real-ESRGAN x4plus 仍使用已有 4× 权重，完成推理后以 Lanczos 缩小至一半，最终输出 2×。
- Upscale 的尺寸计算、界面说明、生产与调试任务统一采用最终 2× 语义；保留现有默认模型。
- PiSA-SR 通过 ONNX Runtime 接入模型下载、设备选择、缓存、取消和资源释放流程，支持任意合法输入尺寸与透明度保留。

## Capabilities

### New Capabilities

- `two-times-upscale`: 四个模型的统一 2× 输出、PiSA-SR 固定细节预设及模型资源生命周期。

### Modified Capabilities

无已发布的对应 capability。

## Impact

- `server/model_catalog.py`、模型下载与导出工具：增加 PiSA-SR 多文件模型资产及校验信息。
- `server/models/`、`server/model_manager.py`：PiSA-SR 推理、分块及多 Session 生命周期；旧模型结果缩小。
- `operators/upscale.py`、模型选择与相关界面：模型选项和最终倍率。
- 生产、调试、透明图片和多帧处理相关测试。运行时沿用 ONNX Runtime；PyTorch 等仅用于离线导出与数值验证。
