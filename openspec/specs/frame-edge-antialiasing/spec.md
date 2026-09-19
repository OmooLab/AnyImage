# frame-edge-antialiasing Specification

## Purpose
TBD - created by archiving change enable-image-alpha-blending-and-premul. Update Purpose after archive.
## Requirements
### Requirement: Frame samples geometric boundary coverage

Frame SHALL 在输出像素与源投射轮廓或前后层级交界相交时使用固定 4×4 均匀子像素中心样本，分别判断有效覆盖及深度顺序。每个样本 SHALL 沿用现有底层 RGB 打底、前景预乘采样与独立 Alpha 合成公式。

#### Scenario: An opaque tilted edge covers half a pixel

- **WHEN** 单张不透明图片仅覆盖该像素的 8 个子样本，其余 8 个没有源覆盖
- **THEN** 输出 Alpha SHALL 为 0.5
- **AND** 该像素 SHALL 不因中心点位于边缘某一侧而变为全有或全无

#### Scenario: The center misses a narrow projection

- **WHEN** 像素中心未命中投射，但 4×4 网格存在有效命中
- **THEN** 有效子样本 SHALL 参与边界合成

#### Scenario: Depth order changes inside a pixel

- **WHEN** 两个源平面在像素覆盖区域内交换前后关系
- **THEN** 每个子样本 SHALL 使用自己的深度顺序
- **AND** 同深度 SHALL 沿用 active 置顶及现有稳定顺序

### Requirement: Frame resolves RGB and alpha with independent coverage weights

边界像素 Alpha SHALL 为全部 16 个子样本 Alpha 的算术平均，无源样本贡献零。RGB SHALL 为具有几何源覆盖的子样本合成 RGB 的等权平均，SHALL NOT 以源 Alpha 作为 RGB 平均权重。全无覆盖像素 SHALL 保持透明黑色，不向 Frame Canvas 外扩展 RGB。

#### Scenario: Mask Add reveals the canvas outside every source

- **WHEN** Frame 范围大于所有源投射，随后 Mask Add 将完全无覆盖区域的 Alpha 恢复为 1
- **THEN** 该区域 RGB SHALL 保持黑色
- **AND** 源边缘颜色 SHALL NOT 形成一像素外框

#### Scenario: A half-transparent foreground partially covers a transparent bottom image

- **WHEN** 透明蓝色底图覆盖全部 16 个样本，Alpha 为 0.5 的红色前图覆盖其中 8 个
- **THEN** 输出 RGB SHALL 为 (0.25, 0, 0.75)
- **AND** 输出 Alpha SHALL 为 0.25

#### Scenario: A white outer edge meets empty canvas

- **WHEN** 不透明白色源覆盖 8 个子样本，其余没有源覆盖
- **THEN** 输出 RGB SHALL 保持 (1, 1, 1)，Alpha SHALL 为 0.5
- **AND** 无源区域的黑色 SHALL 不混入白色边缘

#### Scenario: Transparent layers meet along an oblique boundary

- **WHEN** 子样本合成结果 Alpha 均为零，但各自底层 RGB 不同
- **THEN** 输出 SHALL 保留这些有效 RGB 的覆盖平均
- **AND** Alpha SHALL 保持零

### Requirement: Restoring alpha preserves antialiased layer boundaries

Frame SHALL 将边界颜色过渡存入结果 RGB，使实际 Packed Image 经 Mask Add 后仍保留图层间的抗锯齿过渡。

#### Scenario: Mask Add reveals a tilted foreground over a background

- **WHEN** 倾斜图片与黑色或白色底图合成，经 Pack 后执行 Mask Add 恢复 Alpha
- **THEN** 边界 RGB SHALL 保留子像素覆盖混合的中间颜色
- **AND** Mask Add SHALL 不将边缘恢复为单点覆盖产生的两色跳变

### Requirement: Frame keeps interior detail and bounded output processing

Frame SHALL 对覆盖与层级稳定的内部像素保留现有中心双线性采样。结果 Canvas、输出尺寸限制和对象放置 SHALL 保持原约定；子样本处理 SHALL 按块执行并保持跨块结果一致。

#### Scenario: Pixel-aligned interior contains fine detail

- **WHEN** 原尺寸对齐的图片内部包含交替明暗像素，且该区域没有几何层级边界
- **THEN** 内部 RGB 与 Alpha SHALL 保持现有采样结果

#### Scenario: A boundary crosses processing chunks

- **WHEN** 相同斜边使用不同的行块尺寸执行 Frame
- **THEN** 输出 SHALL 在浮点误差范围内一致
- **AND** 边界 SHALL 不出现行块接缝

#### Scenario: Frame uses the maximum output resolution

- **WHEN** 输出达到配置的最大分辨率
- **THEN** 抗锯齿 SHALL 保持原输出尺寸
- **AND** 系统 SHALL 不为全部源分配完整 4 倍宽、4 倍高的输出副本

