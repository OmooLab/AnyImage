# 烘焙网格

`operators/bake_mesh/operators.py` 定义 `BakeMesh`，固化面片、凹凸面、浮雕、立体全景及受支持的立体裁切节点栈。`materialization.py` 管理网格求值、UV、烘焙和提交；`textures.py` 处理 Color 区域拼接、Alpha 合并及 Emission 编码；`materials.py` 将节点组输出连接到静态贴图。

烘焙读取原材质及 `O Texture to Layer` 的实际参数，使用临时 Cycles CPU 场景，完成后恢复原场景。单区保留 UV，多区按来源区域缩放、平移和翻转 UV。

| 材质输入 | 静态结果 |
| --- | --- |
| Base Color、Alpha | 同一张 RGBA Color 图，保留颜色空间与精度，将计算后的 Alpha 写入 A 通道；浮点 RGB 随 Alpha 调整预乘关系 |
| Roughness | 直接烘焙为 Non-Color PNG 数据图，供 Cycles 与 Eevee 按相同数值读取 |
| Normal | 最终 UV 下的切线空间法线，材质 Normal Scale 为 1 |
| Principled Emission Color | 非负 sRGB PNG，超过 1 的亮度由 Emission Strength 表达 |

成功时保留对象及用户属性，清理已消费的协议属性、修改器和 `o_image_object`。未共享的图片与材质原位更新；存在其他使用者时为当前对象创建独立结果。Alpha 中间图随烘焙资源一起清理。

失败恢复图片与材质输入并释放本次资源；Undo/Redo 恢复网格、贴图和对象状态。回归测试比较真实烘焙前后结果，覆盖两种渲染器的粗糙度和透明度、半透明材质、法线、发光及共享资源。
