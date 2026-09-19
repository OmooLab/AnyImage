## 1. 简化 Selection 值与填充语义

- [x] 1.1 将 Viewport 预览和最终 Mask 统一为 non-zero winding，删除 `EVEN_ODD`、`fill_rule` 参数与分支，并用自交和重复绕行测试验证重叠区始终保留
- [x] 1.2 将 `SelectionPath` 精简为只包含 Points 与 Invert 的不可变值，保留完整值的 `to_json()` / `from_json()`，使共享手势向 Image Tool 和 Cutout Tool 提交完整 Path，并迁移反选相关测试
- [x] 1.3 保持 Cutout Pie Menu 到 `CutoutSelectionToShape` 的单一 `selection_path_json` 边界，用交互测试验证只编码一次、各 Shape 按钮复用同一字符串且恢复相同 Points 与 Invert
- [x] 1.4 删除 `fill_rule` 的序列化、解析和所有兼容入口，使用定向搜索验证业务代码与 Path JSON 均不再包含填充规则

## 2. 局部 Scanline 栅格化

- [x] 2.1 实现 non-zero scanline 端点累计，使每条边只处理实际跨越的像素中心扫描行，并用整数顶点、水平边、凹路径、自交与越界路径测试验证结果
- [x] 2.2 对非 Invert Selection 只建立裁切后的局部画布，抗锯齿时按 5-tap 核增加 2 px padding；对 Invert 保留完整图片画布并验证路径外语义
- [x] 2.3 将源 Alpha 合并限制到当前画布切片，并以按行、按列归约计算紧致 bounds，删除整图 `np.where` 与逐命中像素坐标数组
- [x] 2.4 保持 `SelectionMask`、空 Selection 警告、Image 编辑、AI 输入和 Cutout 几何调用边界不变，用现有像素与几何测试验证下游结果

## 3. 等价性、性能边界与文档

- [x] 3.1 增加小尺寸参考栅格器测试，组合覆盖普通与随机路径、Invert、抗锯齿、随机 Alpha、阈值和空结果，逐值比较 Mask values 与 bounds
- [x] 3.2 增加 5K 多点 Lasso 的工作边界测试，验证不出现逐边的扫描行块乘以宽度数组、局部 Selection 不建立整图 Mask，且不使用机器相关耗时阈值
- [x] 3.3 更新 `docs/internals` 的 Selection 值、Cutout 传输边界、统一 non-zero 语义与局部 scanline 流程，不记录旧兼容路径
- [x] 3.4 运行 Image Selection、Image Tool、Cutout 交互与几何相关测试，运行代表性 5K 基准，再运行 `uv run pytest` 确认全部通过
