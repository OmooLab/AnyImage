## 1. 实施基线

- [x] 1.1 检查当前工作区修改、三个节点组的参数标识和调用顺序，保留已有工作；运行相关边界与深度节点测试，记录基线。
- [x] 1.2 复查独立实验的 Cutout 和 Depth Plane 对比，准备可重建的尖刺、内部孔洞、深度断层及全景接缝／极点合成场景。

## 2. 公共深度平滑

- [x] 2.1 在 common/boundary_smoothing.py 中实现 Point 域标量 Blur、两圈影响权重及保护字段，复用现有节点辅助函数。
- [x] 2.2 实现迭代数为 0 和影响权重为 0 时的原值直通，验证内部精确保持、拓扑不变及分离表面的采样隔离。

## 3. 节点组接入

- [x] 3.1 接入 Depth Cutout，在 Split 后、投影前平滑相机 Z，按原射线重建；让原 Alpha 轮廓参与深度平滑，并保留后置网格平滑的既有保护规则。
- [x] 3.2 接入 Depth Plane，复用原 UV 矩形外框保护，处理 Valid Only 和 Split 的新边界；验证完整矩形的新增深度平滑为恒等操作。
- [x] 3.3 接入 Depth Panorama，在当前球面拓扑上平滑有效径向距离，接回 Depth Scale 表达式；验证 Depth Mask 两分支、UV 接缝和极点。
- [x] 3.4 三组共用 Boundary Smooth 迭代数，保留默认 5、范围 0–20 和既有 socket 标识；更新对应界面描述并精简重复连接。

## 4. 回归与实图验收

- [x] 4.1 为源码构建和保存资产补齐零值直通、边界尖刺、两圈外保持、零深度、相机射线／球面方向及原矩形保护的行为测试。
- [x] 4.2 覆盖 Alpha 与模型 validity 开口、Split 隔离、Cutout 两种模式、零／正厚度及 Depth Scale；检查几何、UV、材质与用户属性传递。
- [x] 4.3 对三张既有实图复验 Cutout 与 Depth Plane，比较 Boundary Smooth 5、12 及不同密度；检查尖刺改善和过度软化，并完成全景专项验收。
- [x] 4.4 递归检查几何组及嵌套组 Capture 为零，审查命名属性的必要性与清理位置，确认节点布局可读。

## 5. 资产与交付

- [x] 5.1 运行 uv run node-group build，更新 O_AnyImage.blend 和必要资产版本标识，在独立 Blender 进程中加载并验证。
- [x] 5.2 运行相关节点及 Operator 测试，确认正常退出；核对源码与资产的一致性、最终差异和旧引用，保留已有其他修改。

## 6. Cutout 轮廓自适应深度平滑

- [x] 6.1 固定 Ratio 0.25–0.5，按当前深度分批更新权重，删除 Weight Blur，保护 Split 切边并沿原相机射线重建。
- [x] 6.2 公开 Outline Smooth Iterations，Boundary Smooth 兼作每批深度步数，更新资产版本及行为测试。
- [x] 6.3 构建验证节点资产，运行相关回归并保存可调实图文件。

## 7. Cutout 输入与轮廓形状精简

- [x] 7.1 固定法线平滑 100、Boundary Smooth 默认 2，Outline Depth Fix 默认 16，彻底删除 Edge Round 形状调整与输入。
- [x] 7.2 更新相关行为测试和版本标识，构建验证资产并刷新可调样例。

## 8. Cutout Options 接口

- [x] 8.1 Front Inflation 改为 0–1 Factor、默认 0；Boundary Smooth 最小值 1；Options 按 Cleanup Threshold、Smooth Weight、Reference Depth、Boundary Smooth、Outline Depth Fix、Front Inflation 排列。
- [x] 8.2 更新接口与默认行为测试、重建验证资产并刷新可调样例。

## 9. Plane 与 Balloon Options 统一

- [x] 9.1 Depth Balloon 前三项为 Cleanup Threshold、Smooth Weight、Reference Depth；Depth Plane 前三项为 Smooth Weight、Reference Depth、Boundary Smooth，Boundary Smooth 默认 2，法线平滑固定 100 并移除输入。
- [x] 9.2 Depth Plane Split Threshold 默认 0.1；验证接口及厚度行为，更新版本并重建验证资产。

## 10. Cutout 求值精简

- [x] 10.1 Front Inflation 为零时旁路膨胀计算，移除共用平滑中的固定选择节点和未使用 Repeat 通道，统一 outline 平滑内部命名。
- [x] 10.2 验证零值及连续膨胀行为、共用平滑结果与性能，重建验证资产。
