# 实现验证

2026-09-14，本机 Windows；资产由 Blender 4.5.10 LTS 构建和重载校验，几何测试及性能测量使用 bpy 4.5.3。

## 几何

- 源码构建和保存资产均验证正面越界删除、完整镜像、边与顶点流形性、面绕序、直壁法线、平滑、空输出和 Depth Axis。
- 测试几何尺度为 0.001、1、100，包含倾斜方向和正面平滑。
- Lasso / Polyline 默认值、模式往返切换与深度校准输入通过对象创建测试。
- 小车 Balloon 分支在默认、单面、零厚度、平滑、坐标轴及方向变化共 5 组参数下，与变更前基准的顶点和面完全一致，最大坐标差为 0。
- 同相机、同参数的小车渲染与已确认布尔原型一致。基准顶点到新网格最近顶点距离中位数为 0，P95 为 6.66e-8，最大值为 0.0361；这是顶点距离比较，不是曲面误差界。整面删除的切口精度受输入网格密度影响。

## 性能

同一小车网格及深度图，Boundary Smooth=3、Smooth=0、Depth Scale=1、Uniform Scale=1、Double Sided=true。Reference Depth=5.5786533，Depth Direction=(-0.6635724, -0.2783087, 0.6944177)。每次只修改所列参数：参考深度或方向 X 分量增加 `0.002*sin(i*0.71)`；预热 4 次，记录随后 24 次依赖图更新耗时中位数。加密输入通过一次 Simple Subdivision 生成，保留 UV。

| 输入顶点 | 修改参数 | 布尔原型 | 正式 Projected | 提速 |
|---:|---|---:|---:|---:|
| 27,860 | Reference Depth | 170.4 ms | 32.8 ms | 5.2 倍 |
| 27,860 | Depth Direction | 173.1 ms | 32.6 ms | 5.3 倍 |
| 165,771 | Reference Depth | 948.3 ms | 147.0 ms | 6.5 倍 |
| 165,771 | Depth Direction | 987.2 ms | 151.5 ms | 6.5 倍 |

本机复核材料在 `C:/Users/icrdr/AppData/Local/Temp/anyimage-car-symmetry/`：`validate_production.py`、`production-validation.json`、`production-baseline.png`、`production-result.png`、`car-depth-symmetry-production.blend`。性能数字为本机对照证据。

## 交付检查

`uv run node-group build` 正常退出，10 个保存节点组通过 Blender 重载校验，附带全量测试 1064 项全部通过（188.83 秒）。源码、测试和构建清单中旧名称引用为零；资产清单验证新组存在且旧组不存在。`openspec validate add-projected-depth-symmetry` 通过。
