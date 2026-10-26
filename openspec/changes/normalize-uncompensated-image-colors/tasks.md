## 1. 颜色求值与固定映射

- [x] 1.1 用 Blender 线性 EXR 路径求值 inverse RGB，对照真实纹理采样，覆盖支持的 inverse 空间及透明 RGB。
- [x] 1.2 在 `common/color_space.py` 实现各通道 `clamp(RGB, 0, 4) / 4`、Gamma 0.75 和 sRGB 编码，保留 Alpha 并拒绝非有限值。

## 2. 共用入口与图像生命周期

- [x] 2.1 集成补偿开关策略，复用已有配置入口和设置读取，更新偏好提示与翻译。
- [x] 2.2 原地写回并打包，保持图像身份、尺寸、Alpha 和绑定，失败恢复原内容及配置。
- [x] 2.3 在重复配置、编辑、颜色图准备和保存重载中传递处理状态；全新原始内容替换时清除状态。
- [x] 2.4 检查材质 `_color` 与三种笔刷入口，覆盖共享引用、笔刷交付回滚及剪贴板缓存失效。

## 3. 整理与验证

- [x] 3.1 提案、设计和规格统一描述固定 T＝4、各通道截断、Gamma 0.75，精简重复测试。
- [x] 3.2 验证数值映射、Alpha、持久化、实际采样和材质笔刷入口；鳄鱼正式入口结果与认可的实验贴图逐像素一致。
- [x] 3.3 运行全量测试并检查退出结果，完成 OpenSpec 严格校验和差异检查。

验证记录：Blender 4.5.3 的相关测试通过；该版本缺少 ACES 1.3 / 2.0，Blender 5.2.2 已单独通过全部五种 inverse 映射与 Cycles 的对照。鳄鱼 T4、Gamma 0.75 正式入口输出及打包重载验证通过。

整理后的全量测试：1000 项及 95 项子测试通过，2 项 ACES 测试跳过，2 项打包测试失败，进程以测试失败码 1 退出。失败来自工作区已有的 Manifest 名称 `Any Image` 与打包逻辑及测试中写死的 `AnyImage` 不一致，涉及 `test_base_contents_and_dependencies` 和 `test_selects_platform_archive_contents_and_manifest`。OpenSpec 严格校验与 `git diff --check` 通过。
