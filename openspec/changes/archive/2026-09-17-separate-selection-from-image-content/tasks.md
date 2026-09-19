## 1. 纯几何 Selection

- [x] 1.1 删除 `rasterize_selection_path()` 的源 Alpha 与 Alpha threshold 参数，使其只按 Path、Invert、图片尺寸和抗锯齿返回几何 `SelectionMask`
- [x] 1.2 调整 Selection 的空路径、越界、Invert、局部画布和 bounds 行为，确保栅格阶段不再承担图片内容可见性判断
- [x] 1.3 更新 Selection 单元测试，验证不同源 Alpha 不参与接口且相同几何输入始终产生相同 values 与 bounds

## 2. 业务侧 Alpha 合并

- [x] 2.1 调整 Image Tool，在几何 bounds 内直接将 Selection 值乘入局部源 Alpha，并由编辑业务计算空内容与最终 placement bounds
- [x] 2.2 移除 Image Tool 对已知局部结果的重复逐像素坐标扫描，使用按行列可见范围完成内容收紧
- [x] 2.3 调整本地 Cutout，使 BaseShape、空内容与几何处理显式消费局部源 Alpha 和纯 Selection 值，不修改 SelectionMask
- [x] 2.4 补充 Image Tool 与 Cutout 的透明、半透明、空内容、Invert 和内容 bounds 回归测试

## 3. 矩形 AI 输入

- [x] 3.1 将 `prepare_selection_input` 替换为统一的 Bounds 图片输入 helper，只裁切源 RGBA 并写出矩形局部文件，不乘入 Lasso Mask
- [x] 3.2 迁移 Image Tool Refine 与 Cutout Refine、Normal、Depth 调用链，使其共享同一个几何 bounds 输入协议
- [x] 3.3 更新 Server 与交互测试，验证 BEN2 可以保留 bounds 内、Lasso 外内容，Normal 与 Depth 不再使用另一套 Masked 输入

## 4. 复用 AI 编码图片

- [x] 4.1 建立加载、配置并 Pack 已编码局部 RGBA 的公共入口，继承源颜色空间、Alpha mode、命名和 placement bounds 所需信息
- [x] 4.2 调整 Image Tool Refine 响应，直接使用 BEN2 输出替换源 Image Empty，删除输出 Alpha 提取、源 RGBA 重读和 Pixel Result Image 重建
- [x] 4.3 调整 Cutout AI 响应：Refine 使用 BEN2 输出，只有 Normal 或 Depth 时使用提交前输入，并让同一局部 Image 同时服务几何 Alpha 与颜色材质
- [x] 4.4 验证成功、取消与异常路径只在结果已加载并 Pack 后清理临时输入，且不残留无用户的 Blender Image

## 5. 文档与验证

- [x] 5.1 更新 Selection、Image Tool、Cutout Tool 与 AI 输出内部文档，区分几何 bounds、内容 bounds 和矩形上下文语义
- [x] 5.2 运行相关测试与完整测试，并用真实高分辨率 RGBA 图片复测 Selection、AI 提交前准备和 AI 响应阶段，确认没有新增第二次图片编码
