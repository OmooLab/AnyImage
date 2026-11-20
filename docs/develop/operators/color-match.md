# 色彩匹配

`SetColorReference` 将选中对象或着色器纹理节点的静态图片设为当前场景的参考图。`properties.py` 同步参考画廊和色板，`common/color_reference.py` 准备参考图的颜色数据。

`MatchColorReference` 在线性 Rec.709 空间匹配色度和亮度。拖动鼠标时，目标对象或纹理节点显示降采样的临时图片。对象与其他物体共用材质时，预览使用独立材质。

取消会恢复原图。确认时先恢复原绑定，校验目标和参考图，再用预览的映射处理全分辨率 RGB，保留 Alpha。结果通过 `ImageEditTarget.commit()` 提交，支持撤销。
