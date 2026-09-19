# ai-operator-failure-handling Specification

## Purpose
TBD - created by archiving change unify-ai-input-validation. Update Purpose after archive.
## Requirements
### Requirement: Expected operator failures are reported normally

AI 操作 SHALL 将输入准备与嵌套 Operator 调用的预期失败转换为普通错误提示和 CANCELLED，包括 Remove BG、Depth/Relief Plane、AI Environment 准备及现有 Panorama 入口。提示 SHALL 保留原因并避免重复的 Blender 错误前缀。

#### Scenario: Nested input validation failure
- **WHEN** 内部 Job Operator 报告无效输入且 bpy.ops 抛出 RuntimeError
- **THEN** 外部入口返回 CANCELLED，显示原因，不向用户展示未捕获的 Python traceback

#### Scenario: Environment setup failure
- **WHEN** AI Environment 设置入口调用安装或下载 Operator 同步失败
- **THEN** 设置入口及调用它的 AI 操作按普通错误取消

#### Scenario: Successful job startup
- **WHEN** 内部 Job Operator 返回 RUNNING_MODAL
- **THEN** 外部入口保持现有成功返回与异步处理语义，源图片及 Undo 行为保持有效

### Requirement: Temporary inputs have explicit ownership

系统 SHALL 释放本次操作创建的临时输入，在准备失败、启动失败、取消及异步结束时均有负责清理的边界；用户原文件 SHALL 保持不变。

#### Scenario: Preparation failure
- **WHEN** packed 图片导出或序列复制失败
- **THEN** 准备函数删除本次临时文件和目录，并保留源图片与源文件

#### Scenario: Synchronous nested failure
- **WHEN** 临时输入准备成功后内部 Operator 抛错或返回 CANCELLED
- **THEN** 临时输入被清理，外部操作取消，源图片引用保持不变

#### Scenario: Asynchronous completion
- **WHEN** Job 接管临时输入并在之后成功、失败或取消
- **THEN** 输入在 Job 结束时清理，运行期间保持可用，用户原文件不被删除

