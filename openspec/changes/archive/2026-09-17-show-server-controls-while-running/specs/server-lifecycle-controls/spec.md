## ADDED Requirements

### Requirement: Running Server lifecycle controls
Server 面板 SHALL 在 Server 的每个 Running 子状态下显示重启和停止控制，并 SHALL 保留该子状态对应的状态文本与图标。

#### Scenario: Server is running and waiting
- **WHEN** Server 状态为 `READY`
- **THEN** 面板显示 Running 状态、重启按钮和停止按钮

#### Scenario: Server is running and busy
- **WHEN** Server 状态为 `BUSY`
- **THEN** 面板显示 Running (Busy) 状态、重启按钮和停止按钮

#### Scenario: Server is not running
- **WHEN** Server 状态不是 Running 子状态
- **THEN** 面板不显示 Running 状态的重启和停止按钮，并沿用该状态对应的现有控制或提示
