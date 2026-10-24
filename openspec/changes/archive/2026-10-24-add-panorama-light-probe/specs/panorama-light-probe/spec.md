## ADDED Requirements

### Requirement: Configurable panorama light probe

系统 SHALL 在 Preferences 提供默认开启的全景 Volume 创建选项，以及以物理米表示、默认 20 m、最小 0.5 m 的单向最大距离。配置与读取入口 SHALL 位于 preferences.py。

#### Scenario: Default configuration
- **WHEN** 用户使用默认配置完成全景生成且存在有效边界
- **THEN** 创建一个 Light Probe Volume，六个方向分别受 20 m 上限约束

#### Scenario: Disabled configuration
- **WHEN** 用户关闭创建选项后生成全景
- **THEN** 仅创建全景结果，距离输入禁用

### Requirement: Evaluated world bounds

系统 SHALL 使用全景求值后网格的世界轴对齐边界，以全景原点为距离参考，按场景 scale_length 换算为米，并逐轴与 `[-x,x]` 求交。

#### Scenario: Asymmetric extent
- **WHEN** 某轴相对原点的范围为 -10.3 至 35 m 且 x 为 20 m
- **THEN** 该轴的截限区间为 -10.3 至 20 m

#### Scenario: Scene unit conversion
- **WHEN** scale_length 为 0.01 且世界空间长度为 320 BU
- **THEN** 尺寸计算使用 3.2 m，最终 4 m 探针对应 400 BU

#### Scenario: Empty or invalid extent
- **WHEN** 求值网格没有有效面、边界非有限或某轴与限制区间无交集
- **THEN** 保留生成的全景，跳过探针并报告提示

### Requirement: Volume size and resolution

系统 SHALL 将截限后每轴长度 L 的米数向下取整为分辨率并限制到 1 至 256；尺寸 SHALL 向上取整到整米、至少 1 m 且最多 2x。原本为整米的尺寸 SHALL 保持原值。系统 SHALL 以截限区间中点为初始中心，必要时平移以同时满足覆盖和每方向 x 的硬上限。

#### Scenario: Requested dimensions
- **WHEN** 截限后长度为 3.2 × 2.5 × 30.3 m
- **THEN** 分辨率为 3 × 2 × 30，尺寸为 4 × 3 × 31 m

#### Scenario: One side reaches limit
- **WHEN** 某轴截限范围为 [-10.3,20] m，x 为 20 m
- **THEN** 探针该轴范围为 [-11,20] m，中心偏移 +4.5 m

#### Scenario: Both sides reach limit
- **WHEN** 某轴截限范围为 [-20,20] m
- **THEN** 该轴尺寸为 40 m，分辨率为 40，中心与全景原点对齐

#### Scenario: Small extent
- **WHEN** 有效网格某轴长度小于 1 m 或为零
- **THEN** 该轴分辨率为 1，尺寸为 1 m，位置满足范围限制

#### Scenario: Fractional maximum distance
- **WHEN** x 为 20.2 m 且某轴同时触及两侧限制
- **THEN** 该轴尺寸为 40.4 m，分辨率为 40

### Requirement: Transactional probe creation

系统 SHALL 在主线程将探针创建到全景结果集合并作为全景的子物体，设置父级时保持计算得到的世界变换，配置世界位置、尺寸和分辨率，保持全景结果为活动选择，并将探针纳入同一次转换撤销和失败清理。系统 SHALL 在提交转换前自动完成新建探针的隔离烘焙。

#### Scenario: Undo conversion
- **WHEN** 用户撤销成功的全景转换
- **THEN** 全景结果和探针一起撤销，源 Empty 恢复

#### Scenario: Creation failure
- **WHEN** 探针创建、配置或烘焙发生异常或取消
- **THEN** 清理本次探针对象、无用户探针数据块和其他转换产物，保留源 Empty

#### Scenario: Parent transform
- **WHEN** 探针设为带有非均匀缩放的全景物体的子物体
- **THEN** 初始世界位置与尺寸保持计算结果，后续随父物体变换

### Requirement: Isolated automatic bake

系统 SHALL 关闭 Volume 的 Capture → Contributions → Indirect Light，保留 Emission 并关闭 World 捕获。系统 SHALL 在烘焙期间仅让本次全景参与捕获，隔离其他物体、灯光与实例，仅烘焙新建探针，并在真实烘焙完成后提交转换。

#### Scenario: External lighting and geometry
- **WHEN** 场景含其他强光、发光物体、遮挡物和集合实例
- **THEN** 新探针缓存仅来自全景，其他物体不贡献照明或遮挡，已有探针缓存保持完整

#### Scenario: Capture contributions
- **WHEN** 新探针创建完成
- **THEN** capture_indirect 为 False，capture_emission 为 True，capture_world 为 False

### Requirement: Restore bake state

系统 SHALL 在成功、失败或取消后恢复所有为烘焙临时修改的场景状态，包括可见性、捕获标志和渲染引擎。成功时激活全景，失败时恢复原选择及活动对象并清理本次产物。

#### Scenario: Successful bake
- **WHEN** 新建探针完成烘焙
- **THEN** 场景原有隐藏状态和引擎恢复，全景为活动对象，Volume 保持父子关系且具有有效缓存

#### Scenario: Failed or cancelled bake
- **WHEN** 烘焙报错或取消
- **THEN** 所有临时隔离状态恢复，源 Empty 及原选择恢复，本次全景、探针和缓存产物被清理
