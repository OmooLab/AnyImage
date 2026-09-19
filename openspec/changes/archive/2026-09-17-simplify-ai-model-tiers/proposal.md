## Why

当前模型选项的资源梯度和用途不够清晰，PiSA-SR 的下载体积与实际效果不符合使用需求，背景移除也缺少轻量默认模型。HAT Sharper 已通过本地效果比较和 ONNX 验证，适合将三个 AI 功能统一整理为各三档，并完成退役模型的资产清理。

## What Changes

| 功能 | 第一档，默认 | 第二档 | 第三档 |
|---|---|---|---|
| Depth | MoGe-2 ViT-S Normal | MoGe-2 ViT-B Normal | MoGe-3 ViT-L |
| Upscale | Real-ESRGAN General WDN x4v3 | Real-ESRGAN x4plus | Real HAT GAN x4 Sharper |
| Remove Background | BiRefNet Lite | BEN2 | BiRefNet HR-matting |

- **BREAKING**：移除 MoGe-2 ViT-L Normal、SAFMN、PiSA-SR 的正式选项和实现；清理 DA3 的现行残留及对应本地、R2 模型资产。
- **BREAKING**：背景移除默认模型改为 BiRefNet Lite，模型选择、AI 环境初始化、下载和缓存统一按背景移除职责组织。
- 接入 HAT Sharper，采用已验证的 FP16 权重存储、FP32 运算 ONNX 路径，沿用最终 2× 输出，完成适配 HAT 的分块验证。
- 接入 BiRefNet Lite 与 HR-matting，按官方预处理和 Alpha 输出语义验证 Lite 的 CPU / DirectML 和 HR-matting 的 CPU、效果、体积和资源占用；HR 选项明确标注 CPU。
- 九款正式模型统一驱动界面、下载、就绪判定和 `model prepare` / `model sync`；清理退役源码、导出器、专用依赖、缓存及远端对象。

## Capabilities

### New Capabilities

- `ai-model-tiers`：三类各三款模型、默认选择及初始化下载行为。
- `background-removal-models`：三款背景模型的选择、推理、Alpha 契约和资源生命周期。
- `hat-upscale`：HAT Sharper 的小体积 ONNX、2× 输出和分块处理。
- `model-asset-retirement`：正式模型资产准备、镜像校验和退役对象清理。

### Modified Capabilities

当前 `openspec/specs` 尚无已发布 capability。本提案承接已有 MoGe-3、2× Upscale 和 HDR 输入实现，以本次模型矩阵确定后续正式选项。

## Impact

- `server/model_catalog.py`、`preferences.py`、`properties.py`、AI Setup 与相关 Operator：模型分类、默认值和下载选项。
- `server/models`、`server/model_manager.py`、背景移除 Job：模型适配、推理分派、会话复用与释放。
- `tools/models`、`pyproject.toml`、`uv.lock` 及相关测试：可复现导出、专用依赖清理和资产校验。
- 项目模型目录、开发缓存与 `omoolab-r2:ai-models`：新资产发布和退役对象清理。
- 本次生成规划文件；实施验证结果记录在 change 内，运行时依赖沿用现有 ONNX 体系。
