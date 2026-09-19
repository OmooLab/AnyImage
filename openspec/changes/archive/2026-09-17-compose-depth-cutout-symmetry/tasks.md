## 1. 对称节点

- [x] 1.1 保存原 Projected 的小型确定性基线数据，覆盖关闭额外平滑后的顶点位置、面连接和朝向。
- [x] 1.2 将 `O Image Cutout Symmetry` 改为几何处理节点，保留方向对齐、偏移、负侧面移除、镜像和直壁补面，按设计精简接口并处理几何尺度容差。
- [x] 1.3 实现 Fill Smooth：生成侧壁内部采样，固定接缝并保持镜像配对；关闭补面时跳过，平滑为 0 时使用原直壁。

## 2. 入口与 Shell

- [x] 2.1 将 Cutout 资产中两种 Thickness 默认值设为 0；Depth Solid 创建时按 subtype 分别设置 Balloon 为 1、Shell 为 0.2。更新 Depth Symmetry 创建为 Cutout → Symmetry 两个修改器，保留 Cutout 节点默认参数，沿用通用的手势模式选择、清理阈值与图像标定，为对称节点初始化方向。
- [x] 2.2 修正 Shell 厚度方向使用完整平滑法线，解除相对厚度衰减，保留原正面、零厚度行为和 Balloon 权重逻辑。

## 3. 验证与资产

- [x] 3.1 更新相关入口及接口测试，验证资产两种厚度默认值为 0、Depth Solid 创建值为 1 / 0.2、Depth Symmetry 使用零厚度且切换模式正确；验证两种模式零厚度、Fill Sides 开关与原 Projected 基线一致。
- [x] 3.2 验证 Balloon/Shell 非零厚度的镜像与补面，以及 Fill Smooth 的侧壁位移、接缝固定、封闭性和镜像关系；使用已有两张去背景图片复核外观。
- [x] 3.3 增加薄 Shell 法线方向平滑的有效覆盖，同时验证零厚度、常法线平面及 Balloon 行为。
- [x] 3.4 运行相关测试和 `uv run node-group build`，验证源码与保存资产无 Capture Attribute、临时属性正确清理，检查最终差异；不打包扩展。

## 验证记录

- 后续调整：Fill Smooth 默认值改为 2；两个深度入口均请求 Object 法线并开启材质 Object Space。资产重建及独立校验通过，66 项对应测试通过。
- 81 项相关测试通过，覆盖入口、节点定义与资产、零厚度基线、补面平滑、薄 Shell、材质属性与布局。
- `uv run node-group build` 完成资产生成与独立进程校验；随后的全量测试发现 5 个需要同步的新接口/行为断言及 1 个既有 Depth Plane 边界平滑失败。前 5 个已修正并通过相关复测。
- 既有失败为 `test_validity_cut_smoothing_preserves_original_outline_and_interior`；在内存中恢复 HEAD 版本的两份节点构建模块后仍能复现，本变更未修改该用例或 Depth Plane 平滑逻辑。
- 最终 `uv run node-group build --skip-tests` 正常退出，10 个保存节点组均通过校验；`git diff --check` 通过。
- 两张已去背景的原样例分别检查 Balloon=1、Shell=0.2 和 Fill Smooth=0/3：八组均无边界边或非流形边，镜像位置误差为 0；已检查渲染。结果位于 `C:/Users/icrdr/Desktop/anyimage/post-cutout-symmetry-20260914/applied/`。

