## Why

AI Server 默认安装在用户目录，用户需要在下载前决定磁盘位置。直接编辑 Storage Folder 无法表达识别既有安装和搬迁现有数据的区别，也容易留下旧目录占用空间。

## What Changes

- 安装提示增加 Server Location 选择和实际目录预览；统一选择存放目录，选择 `D:\` 使用并检查 `D:\.anyimage`，选择 `D:\AI` 使用并检查 `D:\AI\.anyimage`。
- 安装入口同时支持识别既有安装：验证成功后直接使用，缺失环境或模型时按需安装。
- Preferences 移除可编辑的 Storage Folder，保留只读实际位置；未安装显示安装按钮，已安装显示迁移按钮。
- 迁移完整 Server 数据，验证新位置可运行并保存配置后删除旧目录，以完成源目录清理作为迁移成功条件；目标非空时报告冲突。
- 按需调整 Python 环境，确保原根目录删除后 Server 仍能运行。

## Capabilities

### New Capabilities

- `server-location-management`: 安装位置选择、既有安装识别、位置展示和安全迁移。

### Modified Capabilities

无。

## Impact

影响 `preferences.py`、`operators/ai_setup.py`、`runtime.py`、类型注册和相关测试。需要验证本地 BlendJob 的环境探测、生命周期及环境重定位能力；必要时在该依赖的职责内提供明确接口。保留已有 storage_root 的实际路径值，作为唯一配置入口。此次仅生成提案。
