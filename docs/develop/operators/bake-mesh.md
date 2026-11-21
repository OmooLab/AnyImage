# 烘焙网格

`operators/bake_mesh/operators.py` 定义 `BakeMesh`，固化面片、凹凸面、浮雕、立体全景及受支持的立体裁切节点栈。`geometry.py` 求值修改器并排布 UV。`materialization.py` 烘焙并提交结果，`textures.py` 拼接 Color、合并 Alpha 并编码 Emission，`materials.py` 将静态贴图接回材质。

烘焙读取原材质及 `O Texture to Layer` 的实际参数，使用临时 Cycles CPU 场景，完成后恢复原场景。单区保留 UV，多区按来源区域缩放、平移和翻转 UV。

| 材质输入 | 静态结果 |
| --- | --- |
| Base Color、Alpha | 将烘焙的 Alpha 合入颜色图，浮点源按 Alpha 调整预乘 RGB，再归一化为 sRGB PNG |
| Roughness | 直接烘焙为 Non-Color PNG 数据图，供 Cycles 与 Eevee 按相同数值读取 |
| Normal | 最终 UV 下的切线空间法线，材质 Normal Scale 为 1 |
| Principled Emission Color | 非负 sRGB PNG，超过 1 的亮度由 Emission Strength 表达 |

成功时保留对象及用户属性，清理已消费的协议属性、修改器和 `o_image_object`。未共享的图片与材质原位更新；存在其他使用者时为当前对象创建独立结果。Alpha 中间图随烘焙资源一起清理。

失败恢复图片与材质输入并释放本次资源；Undo/Redo 恢复网格、贴图和对象状态。回归测试比较真实烘焙前后结果，覆盖两种渲染器的粗糙度和透明度、半透明材质、法线、发光及共享资源。
