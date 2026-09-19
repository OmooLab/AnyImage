## ADDED Requirements

### Requirement: Reliable depth sources retain the tested alpha rule

系统 SHALL 按剪裁 Alpha 定义可见域和8连通分量；供体候选 SHALL 位于同一可见分量内，并满足固定 Alpha ≥ 0.95、Validity > 0.5、有限正深度。系统 SHALL 保留内侧2像素保护及旧版回退规则。

#### Scenario: Low clipping threshold retains translucent edges
- **WHEN** 剪裁 Alpha 为0.1，边缘 Alpha 为0.1且同分量存在可靠核心
- **THEN** 边缘属于可见域但不能充当供体，其深度使用同分量可靠来源补齐

#### Scenario: Narrow component lacks a core
- **WHEN** 分量内缩2像素后没有可靠供体
- **THEN** 使用本分量未内缩的可靠候选；候选也为空时保留该分量原预测

### Requirement: Extension preserves reliable interior and projection

系统 SHALL 沿用旧算法补齐轮廓边缘及可见域外4个深度图像素，使用sigma=0.8、半径3像素的分量内局部平滑。系统 SHALL 保留内部受保护区域及未修补像素，按目标像素射线重建变化像素的XYZ。

#### Scenario: Filtered sampling crosses an outline
- **WHEN** 采样邻域跨越主体轮廓
- **THEN** 邻近透明侧4像素范围提供延伸深度，各分量采用自身供体和平滑输入，其他可见分量保持各自处理结果

#### Scenario: Corrected points retain their pixel location
- **WHEN** 像素继承供体Z
- **THEN** XYZ仍投影至目标像素，归一化投影误差小于1e-6；原Alpha和validity保持不变

#### Scenario: Opaque input and interior validity holes
- **WHEN** 输入完全不透明，或透明图内部存在模型validity孔洞
- **THEN** 完全不透明输入原样返回；内部孔洞只限制供体资格，不扩大轮廓修补区域

### Requirement: Only cutout depth artifacts use corrected frames

系统 SHALL 仅由Cutout深度请求开启延伸，使用同一修复Frame写入深度和Metadata。共享入口默认 SHALL 关闭修复，Normal SHALL 使用原始Frame，EXR A SHALL 保持原Alpha乘原validity。

#### Scenario: Cutout requests depth and normals
- **WHEN** 同一Cutout请求同时生成深度和Normal
- **THEN** 只执行一次模型预测，深度及Metadata来自修复Frame，Normal来自原始Frame

#### Scenario: Other artifact requests
- **WHEN** 普通Depth Plane、全景深度或仅Normal请求运行
- **THEN** 沿用各自原始预测产物行为

### Requirement: Real image verification uses a fixed prediction

验收 SHALL 在工作区外使用用户蜘蛛和头骨原图、固定同一Alpha与预测，在现有几何节点及相同参数下仅替换原始/延伸深度产物，记录截图、耗时与残余问题。

#### Scenario: Full modifier evaluation
- **WHEN** 两张图完成深度产物对照
- **THEN** 全部结果非空、坐标有限、无节点警告，报告一次补边与节点求值的独立耗时，并检查Normal着色
