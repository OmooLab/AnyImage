## ADDED Requirements

### Requirement: Image Empty panorama conversion entry

系统 SHALL 在 Image Empty 的 AnyImage 右键菜单展示 `Convert to Panorama`，调用 `anyimage.convert_to_panorama`。

#### Scenario: Select panorama conversion
- **WHEN** 用户选中静态 2:1 Image Empty 并选择 Convert to Panorama
- **THEN** 提交当前图片及 Alpha 的全景生成任务，使用 Preferences 中的模型、推理级别和分析尺寸

#### Scenario: Unsupported image
- **WHEN** 输入是动画、视频或非 2:1 图片
- **THEN** 提示输入限制并保留源对象

### Requirement: Consume current image alpha

转换 SHALL 直接使用当前源图及 Alpha。背景处理由用户通过现有 Remove Background 完成。

#### Scenario: Already removed background
- **WHEN** 源 Empty 的天空已透明
- **THEN** 当前 Alpha 进入全景任务，转换过程中只运行几何模型

### Requirement: Complete conversion transaction

系统 SHALL 在主线程加载结果、打包贴图并创建节点对象，成功后替换源 Empty，并提供完整撤销。

#### Scenario: Successful conversion
- **WHEN** Job 返回有效产物
- **THEN** 创建使用 O Image Panorama 的对象，继承源 Empty 世界变换并以其原点为拍摄中心，激活结果并支持撤销恢复源对象

#### Scenario: Cancelled or failed conversion
- **WHEN** 任务失败、取消或响应时源对象已失效
- **THEN** 清理本任务暂存及未使用数据块，不应用部分转换结果
