# clipboard-image-cache Specification

## Purpose
TBD - created by archiving change unify-material-color-images. Update Purpose after archive.
## Requirements
### Requirement: Clipboard reuse requires an unchanged image

相同剪贴板输入 SHALL 仅复用当前像素、尺寸、颜色空间和 Alpha 模式均匹配缓存基线的有效 Image。缓存验证 SHALL 包括透明区域 RGB，并保持候选图像原有内容与状态。

#### Scenario: Repeated content remains unchanged

- **WHEN** 相同剪贴板内容再次粘贴，缓存图像内容和设置未改变
- **THEN** 系统 SHALL 复用该 Image

#### Scenario: Mask overwrites the cached image

- **WHEN** Mask 修改了独占的剪贴板 Image，修改结果已打包，再次粘贴原始剪贴板内容
- **THEN** 系统 SHALL 加载原始剪贴板内容到另一 Image，保留已编辑图像

#### Scenario: Shared edit leaves an intact candidate

- **WHEN** 编辑产生独立结果，另一个用户仍引用未修改的剪贴板原图
- **THEN** 再次粘贴 SHALL 复用该未修改原图

#### Scenario: Other editing or interpretation changes invalidate a candidate

- **WHEN** 候选图像经过尺寸修改、原生绘制、透明 RGB 修改、颜色空间或 Alpha 模式变更
- **THEN** 再次粘贴 SHALL 跳过已变更候选，使用原始剪贴板内容及其初始解释设置

#### Scenario: Legacy or unreadable cache entry is found

- **WHEN** 候选缺少内容校验基线或无法读取
- **THEN** 系统 SHALL 按未命中处理，并保留已有图像

### Requirement: Clipboard material results stay outside the source cache

剪贴板 Plane SHALL 从有效剪贴板原图按整图范围生成独立材质颜色图。参考图、节点和笔刷的后续粘贴 SHALL 按原图缓存有效性选择 Image。

#### Scenario: Painted material is followed by another paste

- **WHEN** 用户粘贴为 Plane 并绘制其材质，随后把相同内容粘贴为参考图、节点或笔刷
- **THEN** 系统 SHALL 使用原始剪贴板内容，且不复用材质颜色图

