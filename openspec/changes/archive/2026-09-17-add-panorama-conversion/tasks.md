## 1. 全景后端

- [x] 1.1 将原型的投影、周期距离融合和参考距离计算迁移到正式 Server 模块，保留解析几何测试
- [x] 1.2 为现有 MoGe2 ONNX 推理增加已知 FOV 的几何恢复，复用模型会话并验证普通图片回归
- [x] 1.3 实现 generate-panorama-geometry Job、尺寸和有效性检查、取消与清理，导出当前颜色、深度及全景元数据
- [x] 1.4 验证源 Alpha 与 Mask 仅在深度导出合成一次，覆盖透明视图、全局无有效数据和跨经度接缝

## 2. 全景节点资产

- [x] 2.1 在本仓库实现 Quad Sphere 及校正子组的资产构建，创建 O Image Panorama 的细分、球面 UV 和 Depth Scale
- [x] 2.2 复用深度 EXR 加载与 Alpha 剔除，保持几何节点单深度图片输入
- [x] 2.3 提取共享 Split Threshold 机制并同步适配现有调用，将径向距离判断、面角重定位和条带清理接入全景
- [x] 2.4 覆盖阈值旁路、断层强度、尺度不变性、连续斜面、经度接缝、极点及条带清理，并运行现有深度表面回归

## 3. 菜单与对象转换

- [x] 3.1 实现 ConvertToPanorama 与 GeneratePanorama，接入 Preferences、输入暂存、Job 参数与注册清单
- [x] 3.2 在 Image Empty 的 AnyImage 菜单添加 Convert to Panorama，验证静态 2:1 输入限制及当前 Alpha 传递
- [x] 3.3 实现主线程结果加载、材质、全景对象和修改器，覆盖源变换继承、替换、撤销及失败清理

## 4. 集成验证

- [x] 4.1 通过既有离线节点资产流程更新 O_AnyImage.blend，验证新进程加载和打包后独立求值
- [x] 4.2 使用已去天空的真实全景与解析样本检查正式菜单流程和 Split Threshold，运行完整测试并检查最终差异
