# Color Match

`operators/color_match.py` 实现 `MatchColorReference`，读取当前 Scene 参考并处理 Image Empty、AnyImage 图片 Mesh 或活动 Image Texture。参考画廊和色板由 `properties.py` 同步，参考数据由 `common/color_reference.py` 准备。

匹配以线性 Rec.709 像素计算色板锚点色度迁移与独立亮度分位曲线。交互使用代理像素、固定 sRGB GPU 浮层和刷新节流；确认时复用代理映射处理全分辨率 RGB，并保留 Alpha。参考与目标的身份、解释设置及实际内容在提交前校验。

结果通过 `ImageEditTarget.commit()` 提交，保留共享图片隔离与 Undo。确认、取消和失败释放纹理、timer、handler、目标像素与参考交互引用。
