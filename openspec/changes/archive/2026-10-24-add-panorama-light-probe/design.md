## Context

`create_panorama_from_result` 在主线程创建带几何节点修改器的全景物体，并通过 `finalize_object_result` 替换源 Empty。探针边界必须取修改器求值后的网格；底层 mesh 只有一个顶点。

## Goals

自动创建适合全景范围的 Light Probe Volume，以明确的米制规则控制覆盖范围和采样数量，保持创建和撤销完整。

## Decisions

### Preferences

在 `preferences.py` 定义 `panorama_light_probe_enabled`（默认 True）与 `panorama_light_probe_max_distance`（默认 20 m，最小 0.5 m），读取也统一在该文件实现。界面显示“全景光照探针”和“单向最大距离”，关闭开关时距离输入禁用。距离保存为物理米数，界面明确标注 m，避免 AddonPreferences 被不同场景的单位比例重新解释。

### 边界与单位

使用求值后实际网格的世界空间轴对齐边界，计入对象缩放。以全景物体世界原点为参考，乘 `scene.unit_settings.scale_length` 转换到米；单位系统为 None 时仍按该比例换算，默认 1 BU = 1 m。

每轴网格区间与 `[-x, x]` 求交，得到 `[a, b]`，长度 `L = b - a`。正负方向独立截限。无有效面、非有限坐标或任一轴无交集时跳过探针并报告提示，全景结果仍保留。退化的零宽轴按最小尺寸处理。

### 尺寸、中心与分辨率

每轴独立计算，所有长度均为米：

1. 分辨率 `R = clamp(floor(L), 1, 256)`，使用 Blender Volume 的 `resolution_x/y/z`。
2. 尺寸 `D = min(max(ceil(L), 1), 2*x)`。浮点计算需在整米附近作小容差归整，避免精度误差引入多余一米。
3. 初始中心 `C = (a+b)/2`，再限制到 `[-x+D/2, x-D/2]`，使取整后仍遵守硬上限并覆盖截限区间。
4. 转换回 Blender 单位，创建世界轴对齐 Volume；根据 Blender 原生探针局部范围设置 scale，并用实际边界验证。对象链接到同集合，名称使用全景名加 `Light Probe`。设全景为 parent，通过父逆矩阵及世界矩阵保持刚计算的世界位置、方向和尺寸，避免重复应用父级缩放；之后随全景移动、旋转和缩放。

| 截限后长度 | 分辨率 | 探针尺寸 |
| --- | --- | --- |
| 3.2 × 2.5 × 30.3 m | 3 × 2 × 30 | 4 × 3 × 31 m |
| 3 × 2 × 30 m | 3 × 2 × 30 | 3 × 2 × 30 m |
| 0.2 × 0.5 × 0 m | 1 × 1 × 1 | 1 × 1 × 1 m |

例如 Z 为 `[-10.3, 20]`，扩展为 `[-11, 20]`，中心为原点的 Z + 4.5 m。两侧均达到 20 m 时尺寸为 40 m。若 x 为小数且两侧都触及上限，硬上限优先，尺寸可为小数。

该规则以用户给定的分辨率与尺寸为契约；采样间距是约一米，实际位置由 Blender 网格采样实现决定。

### 创建事务

探针计算和创建放在全景修改器配置完成后、删除源 Empty 前。在 `convert_to_panorama/light_probe.py` 集中边界计算与 `create_panorama_light_probe`；现有 `object.py` 管理整体事务，复用 `common` 中适用的对象处理函数。临时求值 mesh 必须在 finally 中释放。

关闭功能时直接完成原有全景转换。开启时创建 `VOLUME` 数据块与对象并设置尺寸、位置、分辨率及父级，设置 `capture_indirect=False`、`capture_emission=True`、`capture_world=False`，然后执行隔离烘焙。转换完成后仍选中并激活全景物体，两个对象进入同一次 Undo。创建或烘焙异常、取消时先恢复临时场景状态，再清理本次探针对象和无用户数据块，随后走现有全景清理路径，保留源 Empty。

### 隔离烘焙

项目 Blender 4.5.3 RNA 已将 `visibility_collection` 标为 Deprecated。使用临时场景可见性隔离：保存场景中其他对象的 `hide_render`，烘焙期间隐藏它们，包括灯光、发光网格、实例发射器及其他探针；仅使本次全景和探针参与烘焙。保存并临时开启全景的 Volume 捕获可见性。隔离必须作用于渲染依赖图，测试验证集合实例和原本隐藏对象的行为。

关闭 Indirect Light 的同时保留 Emission，World 捕获关闭，使缓存来自全景自发光。临时设置新探针为活动对象，通过 `bpy.ops.object.lightprobe_cache_bake('EXEC_DEFAULT', subset='ACTIVE')` 只烘焙该探针。实施时验证运行上下文及完成语义；若运行时返回异步任务，必须等实际完成或取消后再恢复隔离，不能将启动成功视为烘焙完成。

烘焙所需渲染引擎和上下文在目标 Blender 中验证；如需临时切换到 EEVEE，保存并恢复原引擎。使用 finally 恢复对象可见性、全景捕获标志、引擎与选择状态，成功后再激活全景结果并提交转换。烘焙失败或取消按转换失败处理，源 Empty 在成功烘焙前保持存在。已有探针缓存保持完整。

## Risks / Trade-offs

- 大尺寸与高分辨率会增加后续烘焙成本 → 默认每方向 20 m，分辨率遵守 Blender 每轴上限 256。
- 几何节点求值存在开销 → 仅在开启功能时求值一次并及时释放临时网格。
- 探针边界和采样语义受 Blender API 影响 → 实施时在项目 Blender 运行时验证局部范围、世界尺寸与分辨率，测试覆盖单采样轴。

## Validation

验证默认与关闭行为、整数和小数长度、单侧与双侧截限、非默认单位、非均匀与负缩放、空网格、失败清理、撤销及活动选择。补充父级变换保持、捕获开关、隔离烘焙、成功/失败/取消后的状态恢复与已有缓存保护测试。除相关 Preferences、翻译和全景转换测试外，执行小尺寸 Volume 的真实烘焙集成验证，比较隔离场景与加入外部强光、发光物体及遮挡物后的结果。

API 参考：[LightProbeVolume](https://docs.blender.org/api/4.2/bpy.types.LightProbeVolume.html)，[Volume 采样说明](https://docs.blender.org/manual/en/4.2/render/eevee/light_probes/volume.html)。
