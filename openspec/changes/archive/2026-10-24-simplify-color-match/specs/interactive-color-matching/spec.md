## MODIFIED Requirements

### Requirement: Color matching uses a two-axis modal interaction
系统 SHALL 使用单轴 Modal：水平移动调整 Mix，初始值为 50%，范围为 0–100%；垂直移动 MUST NOT 改变匹配参数。Shift SHALL 降低水平调整灵敏度，界面 SHALL 仅显示 Mix 数值和操作提示，数值 MUST NOT 持久保存到 Scene 或 Operator 调整面板。

#### Scenario: User adjusts the match
- **WHEN** 用户水平移动鼠标
- **THEN** Mix 在 0–100% 内更新，预览显示对应结果

#### Scenario: User moves vertically
- **WHEN** 用户仅垂直移动鼠标
- **THEN** Mix 与预览结果保持不变

#### Scenario: User makes a precise adjustment
- **WHEN** 用户按住 Shift 水平移动鼠标
- **THEN** 相同位移产生更小的 Mix 变化

### Requirement: Modal interaction uses a proxy preview
系统 SHALL 以保持目标宽高比、最长边不超过 512 px 的临时 Image 显示居中预览。每次操作 SHALL 计算并缓存代理原图与完整匹配结果，鼠标更新 SHALL 只混合这两份数组，不重复运行 HM–MKL–HM。预览 SHALL 限制刷新频率，MUST NOT 修改正式目标像素或绑定。

#### Scenario: User moves the mouse repeatedly
- **WHEN** 连续鼠标事件改变 Mix
- **THEN** 系统复用同一匹配结果，且正式目标始终保持原状态

#### Scenario: A large target is previewed
- **WHEN** 目标任一边超过 512 px
- **THEN** 预览保持宽高比并将最长边限制为 512 px

### Requirement: Confirmation performs one full-resolution commit
系统 SHALL 在左键或 Enter 确认时，按同一算法与当前 Mix 完成一次全分辨率处理，通过现有图片事务提交为一次 Undo 并清理预览。参考或目标版本失效时 MUST 安全取消且不覆盖外部修改。

#### Scenario: User confirms the preview
- **WHEN** 用户确认且发起目标与参考仍有效
- **THEN** 当前目标收到当前 Mix 的全分辨率结果，操作可一次撤销

#### Scenario: Input changes during preview
- **WHEN** 参考内容或目标绑定在预览后发生外部变化
- **THEN** 系统取消提交并清理临时资源

### Requirement: Interactive controls preserve color matching semantics
系统 SHALL 在线性 RGB 中按 original * (1 - mix) + matched * mix 混合，0% 为原图，100% 为完整匹配结果。Alpha SHALL 原样保留，全部目标 RGB SHALL 使用相同规则。再次匹配 SHALL 以当前像素作为新原图，不创建持久原图备份。

#### Scenario: Mix is zero
- **WHEN** Mix 为 0%
- **THEN** 输出 RGBA 与原图完全一致

#### Scenario: Mix is full
- **WHEN** Mix 为 100%
- **THEN** 输出 RGB 等于完整匹配结果，Alpha 等于原图

#### Scenario: Mix is intermediate
- **WHEN** Mix 为 25%
- **THEN** RGB 为原图的 75% 加完整匹配结果的 25%，不附加其他调节

#### Scenario: A matched image is matched again
- **WHEN** 用户再次匹配已处理的 Image
- **THEN** 系统使用该 Image 当前像素作为本次原图
