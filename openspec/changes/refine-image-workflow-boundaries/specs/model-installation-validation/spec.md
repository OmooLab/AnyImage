## ADDED Requirements

### Requirement: Installation UI uses local fast checks
UI SHALL 通过本地声明文件的存在性和大小判断模型是否已安装。draw 和枚举 SHALL 使用本地信息及 Runtime 已有状态快照；完整内容校验 SHALL 发生于服务端模型加载阶段。

#### Scenario: Installation status is drawn
- **WHEN** Preferences、模型枚举或 Server 面板绘制安装状态
- **THEN** 本次绘制只执行本地快速检查并读取已有快照，不计算 checksum、不请求服务端且不启动服务

### Requirement: Sessions require verified model files
服务端 SHALL 在首次创建模型 Session 前完整验证声明文件的大小和 checksum，并复用文件身份对应的有效校验缓存。校验失败 SHALL 阻止 Session 创建，并记录模型 key 及可读失败原因。

#### Scenario: An installed file has same-size corruption
- **WHEN** UI 判断模型已安装，但其文件同尺寸损坏且服务端请求首次加载
- **THEN** 服务端报告文件校验失败并保留可定位的模型身份，不创建 Session 或执行推理

#### Scenario: Verified files are unchanged
- **WHEN** 模型声明与文件身份未变化，已有完整校验结果
- **THEN** 后续加载复用有效校验结果，已加载 Session 沿用现有复用规则

### Requirement: Invalid installations can be repaired
系统 SHALL 通过已有状态快照为校验失败的模型提供重新下载入口。修复下载 SHALL 沿用原子写入与完整文件校验；成功后 SHALL 清理该模型的失败与失效缓存状态，并使后续 Session 从新文件创建。

#### Scenario: A corrupted installed model is repaired
- **WHEN** 用户从模型校验失败状态执行重新下载且下载校验成功
- **THEN** 错误状态清理，修复后模型可重新加载，其他模型文件和有效 Session 保持其原有生命周期

#### Scenario: Repair download fails
- **WHEN** 修复下载取消或失败
- **THEN** 系统保留可读失败状态和再次修复入口，清理未完成文件，并保持既有完整文件
