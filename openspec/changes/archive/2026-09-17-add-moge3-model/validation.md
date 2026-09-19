# MoGe 3 ONNX 验收

2026-09-10。新增 `MOGE3_VITL`，复用 MoGe 2 的输入准备、0–9 分辨率等级、下载、会话缓存和几何产物。骨干支持动态图片尺寸及 token 数，细化图支持动态点数，正式推理执行三次细化。

## 资产

转换源码：`tools/models/moge3_export.py`。上游提交为 `74fbce054ebed49800de42d0ad0e83495065719a`，权重 revision 为 `184008f877d7ad1ad4c2cd2182a9bd1f63d0e5be`。固定 Torch、ONNX、NumPy 和上游提交后重复导出，两次文件哈希一致。

| 文件 | 字节数 | SHA-256 |
|---|---:|---|
| backbone.onnx | 1324190318 | f21246c6921373c8c79ecdb8c78818a79bd2506c2fb88f4d4cdec21b92f725e3 |
| refiner.onnx | 157729628 | 67ad7297aba18f8ef7939e8f700a5b25c41a19ddb68656bc2cd08b54c248fe2a |

权重内嵌于两个 ONNX 文件。镜像已发布到 `models.omoolab.xyz/moge-3-vitl-onnx/`，使用项目 `ModelManager.download` 下载到新目录，耗时 136.1 秒，大小、哈希及 `ready()` 校验通过。

## 精度与动态配置

参考为原始 MoGe 3、相同权重和三次细化。上游 FlexGEMM 的 `SPCONV_ALLOW_TF32` 独立于 Torch TF32 设置；关闭该选项后进行 FP32 比较。验收脚本预设平均深度相对误差小于 0.1%、99 分位小于 1%、二值 Mask 一致率大于 99.9%。

同一组动态图依次执行以下配置；耗时包含骨干、邻域生成、三次细化和后处理，不包含会话创建。

| 图片宽×高 | tokens | 水平 FOV | Windows CPU | DirectML | DirectML 平均深度相对误差 | 99 分位 |
|---|---:|---|---:|---:|---:|---:|
| 384×256 | 1200 | 自动 | 10.65 s | 4.86 s | 0.00216% | 0.02068% |
| 257×385 | 2400 | 90° | 22.92 s | 9.67 s | 0.00228% | 0.01823% |
| 320×320 | 3600 | 自动 | 36.41 s | 17.11 s | 0.00167% | 0.01609% |

三项均通过 CPU 和 DirectML 容差，二值 Mask 一致率为 100%。正式模块使用现有 MoGe 2 后处理，等级 0/9 的平均点图相对误差约 0.00217%/0.00173%，平均法线角误差约 0.006°，归一化内参最大绝对偏差小于 0.000002。2400 tokens 是图层测试值；公开等级继续按原公式映射至 1200–3600 tokens。

## 工作流与平台

| 平台 / Runtime | 验收结果 |
|---|---|
| Windows / DirectML 1.24.4 / RTX 5070 Ti | 动态精度、深度、裁切、12 视图全景通过；纯 ONNX 环境 |
| Windows / CPU | 动态精度通过；原型 CPU Runtime 为 1.29.0 |
| Linux x64 / CPU 1.24.4 / Python 3.12 | 使用项目声明的正式依赖，深度、裁切、12 视图全景通过 |
| macOS / CPU、CoreML | 当前没有可用设备，待实机验收 |

真实 Job 调用仅替换进度/取消传输上下文，图片准备、模型管理、推理、几何处理与文件写入均使用项目代码。Windows 深度、裁切、全景分别约 9.81、5.45、67.13 秒；Linux 分别约 19.19、9.10、112.10 秒。深度/裁切生成 EXR、元数据及法线，全景完成 12 个 90° 视图推理和径向融合并生成 EXR 与元数据。

DirectML 的主要网络计算在 GPU 执行，部分 Gather、Unsqueeze、Concat、Less、Cast、ReduceSum 由 ONNX Runtime CPU 提供程序执行。正式环境依赖保持原样，未引入 Torch、FlexGEMM 或 Triton。

等级 0/9 连续运行时，Windows 进程峰值工作集约 1483 MiB；显卡整体占用由 6370 MiB 上升至最高 15716 MiB（每 0.5 秒采样，包含桌面及其他进程，不能视为模型独占显存）。Linux 三个 Job 进程峰值 RSS 约 4664 MiB。高等级的内存占用明显高于低等级。

## 回归与复现记录

全量 pytest：1143 passed、52 subtests passed，187.79 秒，正常退出。随后新增会话加载失败恢复测试，MoGe 3 专项 7 passed。覆盖下载完整性、缓存复用/切换/恢复、三次细化、尺寸、参数及现有 Alpha、FOV、取消、全景融合和打包内容契约。OpenSpec 严格校验通过。

实验与运行日志保存在 `C:/Users/icrdr/AppData/Local/Temp/anyimage-moge3-trial/`：`dynamic_reference.py`、`dynamic_validate.py`、`production_validate.py`、`job_validate.py`、`linux_jobs.py`、`download_validate.py`、`memory_validate.py`，及对应 JSON/日志。Linux 使用只读项目挂载的 Python 3.12 容器；Windows 全量测试使用按项目锁文件创建的独立测试环境。

任务 3.3 保留未完成状态，待补充 macOS 实机验收。
