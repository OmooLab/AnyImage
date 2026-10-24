## ADDED Requirements

### Requirement: Model status uses stable catalog identities
服务端加载状态 SHALL 以稳定模型 key 表示每个已加载模型，空槽 SHALL 使用明确空值。模型目录 SHALL 声明档位，Preferences、模型枚举和 Server Panel SHALL 从该目录读取显示名称与档位。

#### Scenario: A display name changes
- **WHEN** 模型 label 改变但模型 key 与档位声明保持不变
- **THEN** 加载身份和档位保持正确，界面使用更新后的显示名称

#### Scenario: Catalog entries are reordered
- **WHEN** 模型目录中的条目顺序调整
- **THEN** 各模型的 Fast/Base/Pro 档位保持其显式声明值

#### Scenario: Loaded state is displayed
- **WHEN** Server Panel 读取已加载与空模型槽
- **THEN** 当前任务行、加载指示与卸载入口保持原有布局，档位由非空模型 key 对应的目录记录提供
