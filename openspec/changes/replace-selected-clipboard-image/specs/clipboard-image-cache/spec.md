## ADDED Requirements

### Requirement: Replacement uses cached content according to actual references

显式替换 SHALL 将缓存用作输入，独占目标保留 Image ID，共享目标分离独立 Image。读取、颜色处理和清理 SHALL 区分原图、结果图、借用缓存与操作自有临时 Image。替换成功后 SHALL 仅清除结果图旧剪贴板哈希及内容基线；共享原图及普通创建粘贴 SHALL 继续遵循原有缓存有效性规则。

#### Scenario: Cached input belongs to another user
- **WHEN** 新剪贴板内容命中另一个 Image，且该缓存被其他对象使用
- **THEN** 替换 SHALL 将输入内容写入按引用规则确定的结果 Image，保留缓存 Image 及其内容和引用

#### Scenario: Cached input is the target
- **WHEN** 缓存命中的 Image 就是独占替换目标
- **THEN** 系统 SHALL 保持该 Image 身份与引用，成功后保持有效 packed 内容，清理不得删除目标

#### Scenario: Cached input is shared by the target and another user
- **WHEN** 缓存命中的 Image 同时被当前目标和其他实际使用者引用
- **THEN** 当前目标 SHALL 获得独立 Image，原缓存图的内容、标记与其他引用保持

#### Scenario: Paste the old clipboard after replacement
- **WHEN** 原缓存 Image 已被替换成另一内容，用户取消目标选择后再次粘贴旧剪贴板内容
- **THEN** 创建粘贴 SHALL 获取旧剪贴板的有效输入，已替换 Image 保持新内容

#### Scenario: Normalize brush input from a shared cache
- **WHEN** 笔刷替换使用了其他用户引用的原始缓存 Image
- **THEN** 系统 SHALL 仅对准备交付的内容执行现有归一化，缓存 Image 保持原内容，目标获得一次归一化后的新内容
