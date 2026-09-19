# server-cache-display Specification

## Purpose
TBD - created by archiving change show-server-controls-while-running. Update Purpose after archive.
## Requirements
### Requirement: Cached model list layout
Server 面板 SHALL 显示所有 Cached 模型名称，并 SHALL 在存在多个模型时让每个模型名称占据独立的视觉行。

#### Scenario: Multiple models are cached
- **WHEN** Server 为 Running 且 Cached 列表包含两个或更多模型
- **THEN** 面板逐行显示每个模型名称，并保留缓存清理按钮

#### Scenario: One model is cached
- **WHEN** Server 为 Running 且 Cached 列表只包含一个模型
- **THEN** 面板在一行内显示 `Cached` 与该模型名称，并保留缓存清理按钮

#### Scenario: No model is cached
- **WHEN** Server 为 Running 且 Cached 列表为空
- **THEN** 面板显示 `Cached: None`，并保留缓存清理按钮

