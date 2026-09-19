## 1. Server Panel 布局

- [x] 1.1 统一 `READY` 与 `BUSY` 的 Running 判定，让状态标签、重启按钮、停止按钮和 Cached 区域复用同一分支
- [x] 1.2 调整 Cached 模型布局：空列表和单模型保持单行，多个模型使用逐项纵向 Label，并保留清理按钮

## 2. UI 行为验证

- [x] 2.1 补充 Server Panel 测试，验证 `READY` 与 `BUSY` 都显示重启和停止按钮，非 Running 状态不显示这些按钮
- [x] 2.2 补充 Cached 列表测试，验证零个、一个和多个模型的文本、分行与清理按钮
- [x] 2.3 运行相关测试与完整测试套件，确认 Server Panel 和既有 Add-on 行为通过
