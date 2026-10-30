## MODIFIED Requirements

### Requirement: Running Server lifecycle controls
Server 面板 SHALL 使用统一状态和默认控制 UI；停止与重启 SHALL 协调全部未结束 Job。

#### Scenario: Server is running and waiting
- **WHEN** Server 状态为 IDLE
- **THEN** 面板显示空闲状态、重启和停止按钮

#### Scenario: Server is running and busy
- **WHEN** Server 状态为 PROCESSING
- **THEN** 面板显示处理中状态、重启和停止按钮，任务进度在侧边栏逐行显示

#### Scenario: Server is not running
- **WHEN** Server 状态为 OFFLINE 或 ERROR
- **THEN** 提供启动入口；STARTING、STOPPING 和维护期间显示各自状态及适用控制

#### Scenario: Stop or restart a queue
- **WHEN** 用户停止或重启带有多个任务的服务器
- **THEN** 阻止新提交，取消并清理全部未结束任务，停止服务；重启操作随后重新启动服务器
