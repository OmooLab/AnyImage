## Context

See `proposal.md` - Why。当前 `ModelManager` 按 BEN2、Geometry 与 Upscale 三类缓存 ONNX `InferenceSession`；模型适配器各自直接调用 `session.run()`。Session 释放时的 `gc.collect()` 会连同模型一起丢弃，无法满足只清理单次推理内存的目标。

四类模型具有不同的运行粒度：BEN2 可逐帧执行，DA3 可 joint 或 per-frame 执行，MoGe-2 可依次处理多张图，Upscale 会把每帧拆成多个固定 tile。临时 arena 应在完整业务推理的最后一次 `session.run()` 后回收，而不是在内部每次运行后回收。

ONNX Runtime 的 arena shrinkage 通过最后一次 Run 的 `RunOptions` 发起。CUDA 默认的 `kNextPowerOfTwo` arena 不保证首个分配区域可收缩，因此需要为所有 CUDA 模型 Session 使用 `kSameAsRequested`；Session 与仍被模型使用的分配保持存活，只回收空闲区域。

## Goals / Non-Goals

**Goals:**

- 让所有 ONNX 模型通过一个共享运行边界选择 Provider 安全的临时内存释放行为。
- 保持模型 Session、权重与执行计划缓存，下一次匹配请求不重新加载。
- 把释放点放在单图、完整帧集合或完整 tile 集合的最后一次模型运行。
- 保持 CPU、DirectML、CoreML 与现有 Provider fallback 行为不变。

**Non-Goals:**

- 不释放 Blender 当前显示图片所占用的纹理显存，也不改变结果图片分辨率。
- 不保证失败或取消发生在中间运行时仍能在不销毁 Session 的前提下立即收缩 arena；既有 OOM Session 失效策略保持不变。
- 不引入 PyTorch CUDA allocator、外部 allocator 或新的运行依赖。
- 不调整模型族缓存数量、切换模型时的淘汰规则或 `Clear Models` 行为。

## Decisions

### 1. Session 创建与 Session 运行共享同一套内存策略

`server/models/onnx_runtime.py` 扩展为唯一策略入口：

- `create_session()` 在选中 CUDA 时附加 `arena_extend_strategy=kSameAsRequested`；其他 Provider 保留现有配置。
- 共享的模型运行函数接收“本次运行结束业务推理”的布尔值。仅当该值为真且 Session 实际使用 CUDA 时，创建 `RunOptions` 并设置 `memory.enable_memory_arena_shrinkage=gpu:0`。
- 未请求释放或 Provider 不支持时，直接执行原 `session.run()`，不构造无效配置。

不把清理放进 `ModelManager`：Manager 只知道 Session 的缓存与淘汰，不知道一次模型调用是不是多帧或多 tile 的最后一次运行。也不在任务结束时销毁 Session，因为这会丢失模型缓存。

### 2. 低层模型运行显式接收完成边界

BEN2、DA3、MoGe-2 与 Upscale 的 ONNX 适配器不再直接调用 `session.run()`，统一调用共享运行函数，并接受是否在本次运行后释放临时内存的参数。单次调用默认把自身视为完整业务推理；批处理编排方对中间运行显式传入 false，仅对最后一次传入 true。

选择显式参数而不是全局状态或计数器，因为 Server 虽是单 Worker，模型入口仍同时服务生产 Job、Selection 与 Debug Job。调用方掌握准确的输入数量与 tile 数量，显式传递不会让取消、异常或嵌套调用破坏隐式计数。

### 3. 每种批处理在已有所有者处标记最后一次运行

- BEN2 的多帧入口只让最后一帧释放；单图 Remove Background 与 Refine Selection 直接释放。
- DA3 joint 模式在唯一一次运行后释放；per-frame 模式只让最后一帧释放。
- MoGe-2 的多图入口只让最后一张释放；单图 Artifact 与直接调试入口释放。
- Upscale 的 tile 循环可确定最后一个 tile；上层多帧 Job 只让最后一帧的最后一个 tile 释放。生产与 Debug 的帧循环使用相同边界。

不选择每次 `session.run()` 后都收缩，因为视频、DA3 per-frame 与 Upscale tile 会在下一次运行立即重新分配同类空间，增加同步与 allocator 开销而没有为 Blender 提供中途使用显存的机会。

### 4. 清理能力按 Session 的实际 Provider 判定

判断依据是 Session 的实际 Provider，而不是用户请求的 Device。这样 CUDA 请求回退到 DirectML 或 CPU 时不会错误提交 `gpu:0` arena 配置；`auto` 实际选到 CUDA 时仍会启用清理。

本次只对 ONNX Runtime 明确支持的 CUDA GPU arena 使用 shrinkage。DirectML、CoreML、CPU 与其他 Provider 保持普通 Run，避免把 CUDA 配置推广为未经验证的跨 Provider 行为。

### 5. 测试同时固定清理时机与缓存身份

共享 Runtime 测试覆盖 CUDA Session 配置、最终 RunOptions、非 CUDA 普通 Run 与输出透传。各模型测试记录每次运行是否请求释放，分别固定 BEN2 多帧、DA3 两种模式、MoGe-2 多图、Upscale 多帧多 tile 的“仅最后一次”为真。

Server Runtime 测试在推理完成前后比较缓存 Session 身份和加载次数，证明 arena cleanup 不经过 `release_*()`。现有 Upscale OOM 测试继续固定失败时销毁 Session 的既有合同。

## Risks / Trade-offs

- [arena shrinkage 增加一次任务结束时的同步与后续重新分配成本] → 只在完整业务推理末尾执行，不在帧或 tile 内部重复执行。
- [CUDA Provider 配置在不同 ONNX Runtime 版本中存在差异] → 使用项目锁定版本支持的标准 Provider/Run 配置，并用真实 API 冒烟测试与模拟 Session 单元测试共同覆盖。
- [实际显存不会回到模型加载前水平] → 明确只回收空闲推理 arena；模型权重、执行计划和 Blender 正在显示的纹理继续占用显存。
- [调用方漏传最后一次标记会延迟释放] → 单次模型入口默认释放，所有已知批处理入口建立调用序列测试。
- [中间运行取消或非 OOM 异常可能保留 arena] → 保留 Session 缓存优先；下一次成功业务推理会再次执行收缩，显式资源错误继续沿用既有 Session 淘汰路径。

## Migration Plan

1. 建立共享 CUDA Session 配置和 Provider-aware Run 入口及其测试。
2. 迁移四类 ONNX 适配器，保持输出与异常转换不变。
3. 从模型批处理到生产与 Debug Job 逐层传递最后一次运行标记，并覆盖多帧、多图与多 tile 测试。
4. 更新 Runtime 内部文档，运行全部测试。

该变更没有数据迁移。回退时同时回退共享 Runtime 配置、四类适配器参数和调用方标记；模型文件与已生成 Job 产物无需处理。
