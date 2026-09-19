## 实施结果

四个 Upscale 选项统一输出 2×。PiSA-SR 固定像素强度 1.0、语义强度 0.7；旧模型完成原生 4× 拼接后使用 Lanczos 缩半。默认模型与现有 key 保持有效。

PiSA-SR 使用 512 输出 tile、128 像素重叠。固定 seed 42 的 64×64 latent 噪声作为 noise.npy 分发，按整图坐标周期索引，重叠区域使用相同噪声。中间 latent 与像素预测存入任务临时目录，GPU 同时只加载一个组件；最终颜色校正在整图拼接后执行。

正式导出器从固定源码、基础权重和 LoRA 重新生成的四个 ONNX 文件与实验图逐文件 SHA256 相同。发布资产另外写入许可和修改元数据，并随包提供 Apache 2.0、CreativeML Open RAIL++-M 与 NOTICE。最终 8 个文件已上传 R2；远端大小核对零差异，应用实际下载函数完成 noise.npy 的下载与 SHA256 校验。

## 验证

- `uv run --no-sync pytest -q`：680 passed、2 xfailed、60 subtests passed。
- 两张 0.7 样图，DirectML 与 PyTorch 最终成品平均绝对差异分别为 0.693、0.596 个 8-bit 灰度级；CPU 为 0.257、0.569。
- DirectML 测试覆盖 1024×1024、1114×1518、1026×514 和 2×6 输出；完整主体、渐变的目视检查未见明显拼接线。
- 三帧轻微平移、文字和半透明边缘通过生产入口验证；alpha 与源 alpha 直接 Lanczos 放大完全一致。细纹理随帧有变化，文字出现生成型模型的笔画变化。
- Blender 4.5.3 实际 Python 接口验证四个模型枚举、Operator 注册、结果尺寸与图片替换；真实 Undo 测试恢复原图尺寸和像素。窗口菜单未通过鼠标操作，菜单与请求参数由接口测试覆盖。

## 速度与设备

RTX 5070 Ti、其他 GPU 应用同时运行。计时包含阶段加载、采样、拼接和颜色校正；不含模型下载。

| DirectML 输出 | 完整耗时 |
| --- | --- |
| 512 首次 | 5.24 秒 |
| 512 重复 | 4.67 秒 |
| 1024 | 5.55 秒 |
| 三帧逐帧 | 每帧 4.79–5.05 秒 |

采样进程 RSS 峰值约 437 MiB；显卡总占用从约 7985 MiB 到峰值 11930 MiB，包含其他应用，不能视作本进程独占显存。阶段加载约占单张 512 耗时的大部分。

DirectML 和 CPU 完整出图。独立 CUDA ONNX Runtime 1.24.4 配合 torch 2.7.1 的 cuDNN 9.7.1 在本机 VAE 卷积上报 `No valid engine configs for ConvFwd`；该组合未通过 CUDA 验收，运行错误明确提示改选 DirectML 或 CPU，关闭 Session 的运行中隐式回退。CoreML 无可用测试设备，当前 PiSA-SR 明确提示选择 CPU。Windows 的既有生产路径使用 DirectML。

实验日志、输出图片和各阶段计时在 `build/upscale-explore/pisa-research/`。项目运行时依赖与 Manifest 未修改。
