## Why

当前固定颜色迁移无法分别控制色彩和明暗的参考强度。全分辨率处理虽适合单次提交，但不足以随鼠标连续刷新，因此需要轻量代理预览。

## What Changes

- 将 `Match Color Reference` 从立即执行改为鼠标 Modal 交互。
- 水平移动控制 Color 迁移强度，垂直移动控制 Lightness 迁移强度，两者范围均为 0%–100%，初始均为 50%。
- 使用最长边 512 px 的临时代理图片预览，左键或 Enter 确认后才执行一次全分辨率处理。
- 右键或 Esc 取消并恢复原图片绑定；预览过程不写入正式图片或产生多步 Undo。
- 预览显示简洁的 Color 与 Lightness 数值，并支持 Shift 精细调整。
- **BREAKING**：取代初版颜色匹配的固定完整强度和立即提交行为。

## Capabilities

### New Capabilities

- `interactive-color-matching`: 定义二维 Modal 调节、代理预览、确认提交、取消恢复及性能行为。

### Modified Capabilities


## Impact

- 影响颜色匹配算法参数、`MatchColorReference` Operator、图片目标临时绑定与相关菜单/交互测试。
- 继续使用 NumPy、SciPy 与现有 `ImageEditTarget`，不增加依赖或 AI 环境耦合。
