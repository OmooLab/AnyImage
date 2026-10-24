## Context

`ModelSessionCache` 当前按 background、geometry 和 upscale 保存三个 Session，这正好覆盖 Remove Background 与 Cutout 连续使用的热工作集。共享 ONNX Runtime 已能用 `OnnxResourceError` 区分资源失败与普通错误，但只有 Upscale 会局部释放失效 Session，其他模型的 OOM 不会统一清理缓存。

现有 `ClearModels` Operator 通过 Server 的资源清理接口安全卸载全部 Session，Server 忙碌时会拒绝操作；入口目前只在 Server 面板。

## Goals / Non-Goals

**Goals:**

- 正常推理继续保留三个 Session 槽位和热启动行为。
- 加载阶段的资源失败通过一次“清空并重试”消除其他缓存 Session 的干扰。
- 推理阶段的资源失败清空所有 Session，但不重复昂贵推理。
- 让用户从 AnyImage 右键菜单主动卸载模型。

**Non-Goals:**

- 不按空闲时间、显存读数或模型文件大小自动淘汰。
- 不改变缓存槽位数量、模型选择、推理分辨率或 Provider。
- 不为普通错误、任务取消或输入错误清理缓存。

## Decisions

### 1. Session 创建只在资源失败时重试一次

`ModelSessionCache` 使用一个内部加载辅助函数执行 Session factory。首次创建抛出 `OnnxResourceError` 时调用 `close()` 清空三个槽位，再执行同一 factory 一次；第二次失败直接向上传播，缓存保持为空。

重试位于 Cache 层，因为该层同时拥有全部 Session，并能准确区分 Session 创建与后续推理。background 的加载计时包含可能发生的清理与重试，不增加新的计时协议。

### 2. 推理资源失败在统一 Job 边界清理

AnyImage Server 为五个模型推理 Job 使用一个轻量执行辅助函数。它只捕获 `OnnxResourceError`，调用当前 `model_manager.clear()` 后原样重新抛出；下载 Job 不经过该边界。

不在各模型适配器重复添加 try/except，也不自动重试推理。此时失败可能来自当前模型的 activation 峰值，重试通常只会再次耗尽资源。

### 3. 手动清理复用现有 Operator

`draw_image_actions()` 在 AI Environment 已安装时增加 `ClearModels`，因此 Image Empty、AnyImage object 和 Image Texture node 共用同一入口。Operator 的 `poll()` 只允许 Server 状态为 `READY`，防止忙碌时清理，也避免 Server 已停止时为了空操作将其启动。

Server 面板的现有清理按钮继续保留，两处引用同一 Operator，不创建转发 Operator。

## Risks / Trade-offs

- [首次加载 OOM 会丢失 Remove Background 与 Cutout 的热缓存] → 只在操作已经无法继续时清理，并让当前模型获得一次恢复机会。
- [Unicode Provider 错误也属于 `OnnxResourceError`] → 共享 Runtime 已使用保守提示；释放可疑的 Provider Session 比继续持有更安全。
- [第二次加载仍然 OOM] → 不继续重试，保留原错误并确保缓存为空。
- [Job 失败清理与用户手动清理可能并发] → 自动清理在单 Worker Job 内执行；手动接口继续由 Server 拒绝 BUSY 状态。

## Migration Plan

1. 为三类 Session 加载建立统一的一次性资源恢复测试与实现。
2. 为模型 Job 建立统一推理失败清理边界并覆盖成功、资源错误和普通错误。
3. 给 `ClearModels` 增加状态检查并加入共用右键菜单。
4. 运行相关 AI、菜单、面板和注册测试；回退无需数据迁移。

## Open Questions

无。
