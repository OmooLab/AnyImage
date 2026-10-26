## 1. 验证与输入边界

- [x] 1.1 用相关 Blender 测试验证最终 Normal 输出经 Diffuse NORMAL Bake 保留非单位 Normal Scale、正负 Bump 和仅 Bump 的效果，并满足有效 UV 误差阈值。
- [x] 1.2 扩展材质预检，记录 O Image Layer 输入及全部输出消费者，区分 Shadeless、Roughness 烘焙和 Normal 烘焙所需条件。

## 2. 静态贴图与节点

- [x] 2.1 在现有隔离烘焙上下文加入 Roughness EMIT Bake，明确源与目标 UV、区域尺寸、Non-Color 精度和 pack。
- [x] 2.2 调整 Normal Bake，固化实际强度和 Bump，支持新增 Normal 目的地，删除旧重置强度和禁用 Bump 的路径。
- [x] 2.3 构建静态材质输出：Roughness 图、Normal Map、Alpha 曲线、Specular 图和直接 Color 连接；无细节时使用 Geometry Normal。
- [x] 2.4 重接全部原输出消费者并移除结果 O Image Layer 实例，保留组外节点、参数与其他连线。

## 3. 生命周期与提交

- [x] 3.1 复用 common 的共享资源检测和图片恢复能力，扩展节点与连线事务，覆盖准备失败和部分提交失败。
- [x] 3.2 保持无共享既有数据身份，隔离共享材质与图片，处理新增 Roughness / Normal 的提交、失败清理及保存重载。
- [x] 3.3 结果图片使用 `_roughness` 分类；验证现有按归属筛选的 Color Reference 已排除新贴图，保留当前颜色归一化行为。

## 4. 相关行为验收

- [x] 4.1 验证单区、Cutout 多区、旋转 symmetry、深度衰减及退化侧壁的法线和粗糙度结果。
- [x] 4.2 验证 Alpha Fix、Specular 灰度、原消费者连接、Shadeless、共享资源隔离及修改器前缀边界。
- [x] 4.3 注入 Roughness Bake、Normal Bake、图片写入及节点重接失败，验证恢复及临时资源清理；验证 Undo / Redo 和保存重载。
- [x] 4.4 运行本次涉及的 Bake Mesh、图片分类与材质行为测试，确认正常退出；若改动 Blender 类型，同步检查注册和逆序注销测试。


## 5. PNG、高光、发光与布局

- [x] 5.1 将 Roughness 和 Specular 烘焙为独立 0–1 Non-Color PNG，验证线性数值与实际 PNG 编码。
- [x] 5.2 根据原强度断开发光或复制 Color 为 `_emissioncolor`，保留强度及原图精度和解释。
- [x] 5.3 按 Principled 输入顺序排列贴图节点，失败恢复位置与连线。
- [x] 5.4 验证共享隔离、PNG 保存重载、GLB 往返及失败回滚，运行相关测试。


## 6. 统一烘焙颜色

- [x] 6.1 复用固定归一化算法，将 inverse / HDR 转为 0–1 sRGB，避免普通 sRGB 和已归一化图片重复处理。
- [x] 6.2 所有派生贴图基于最终 Color，Specular 直接 RGB to BW；保留可编辑资产的 Clamp。
- [x] 6.3 验证两种颜色补偿偏好产生一致结果，覆盖 HDR、Alpha 和重复处理。
- [x] 6.4 验证写回、共享隔离、保存重载和失败回滚，运行相关测试。
