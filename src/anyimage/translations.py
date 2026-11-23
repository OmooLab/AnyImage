"""Translations for base image workflows, grouped by business responsibility."""


# 公共界面与图像目标
COMMON = {
    'The selected image and its owner must be editable': '所选图像及其所属数据必须可编辑',
    'Only still images are supported': '仅支持静态图像',
    'Image gestures only support a still image': '图像手势仅支持静态图像',
    'The selection contains no visible image pixels': '选区不包含可见的图像像素',
    'The edit contains no visible image pixels': '编辑结果不包含可见的图像像素',
    'Select an Image Empty or a shader texture with an image': '请选择图像空物体或带有图像的着色器纹理节点',
    'The source Image Empty is no longer available': '源图像空物体已不可用',
    'The source image target is no longer available or has changed': '源图像目标已不可用或已改变',
    'The source image content or settings have changed': '源图像内容或设置已改变',
    'The conversion source image has changed': '源图像已改变',
    'Any Image': '任意图！',
    'Start': '启动',
    'Error': '错误',
    'Unavailable': '不可用',
    'Tools': '工具',
    'Automatic Material Preview': '自动材质预览',
    'Show materials after Cutout and use the scene World after World or Panorama conversion': '抠图后显示材质，转换为世界环境或全景后使用场景世界环境',
    'Gesture': '手势',
    'None': '无',
    'Lasso': '套索',
    'Polyline': '折线',
    'Brush': '画笔',
    'Draw a closed freehand area': '自由绘制闭合区域',
    'Click points to define a closed area': '点击多个点定义闭合区域',
    'Paint with a circular brush': '使用圆形画笔涂绘',
    'Settings': '设置',
}


# 剪贴板
CLIPBOARD = {
    'Paste images from a 3D View or Node Editor': '请在 3D 视图或节点编辑器中粘贴图像',
    'Switch to Object Mode before pasting a reference image': '请切换到物体模式后再粘贴参考图像',
    'The clipboard image has invalid dimensions': '剪贴板图像尺寸无效',
    'The Node Editor has no editable node tree': '节点编辑器中没有可编辑的节点树',
    'The image node has no assignable image input': '图像节点没有可赋值的图像输入',
    'The active tool does not provide an editable brush': '当前工具没有可编辑的画笔',
    'The active brush is read-only and cannot be localized': '当前画笔为只读，无法转为本地数据',
    'The active brush still belongs to an external library': '当前画笔仍属于外部资产库',
    'The localized brush is still read-only': '转为本地数据后的画笔仍为只读',
    'Unable to activate the local Brush Asset copy': '无法激活本地画笔资产副本',
    'Blender did not activate a local Brush Asset copy': 'Blender 未激活本地画笔资产副本',
    'Pasted and packed {name}': '已粘贴并打包 {name}',
    'Replaced and packed {name}': '已替换并打包 {name}',
    'Clipboard replacement supports still images only': '剪贴板替换仅支持静态图像',
    'Unable to paste clipboard image: {error}': '无法粘贴剪贴板图像：{error}',
    'Paste Clipboard Image': '粘贴剪贴板图像',
    'Paste and pack the clipboard image for the current editor': '在当前编辑器中粘贴并打包剪贴板图像',
}


# 色彩参考与匹配
COLOR = {
    'Set a color reference before matching': '请先设置色彩参考图',
    'The color reference and target must be different images': '色彩参考图和目标必须是不同的图像',
    'The color reference changed during preview': '色彩参考图在预览期间发生了变化',
    'Color {color:.0f}% | Lightness {lightness:.0f}%': '色彩 {color:.0f}% | 明度 {lightness:.0f}%',
    'Fine Adjustment': '精调',
    'The color reference is no longer available': '色彩参考图已不可用',
    'The color reference contains no visible pixels': '色彩参考图不包含可见像素',
    'Color Match': '色彩匹配',
    'Reference': '参考图',
    'No color reference': '无色彩参考图',
    'Set Color Reference': '设为色彩参考图',
    'Match Color Reference': '匹配参考图色彩',
    'Match this image to the current color reference': '将此图像的色彩匹配到当前参考图',
}


# 重设画框
FRAME = {
    'Frame\u200b': '重设画框',
    'Frame only supports still images': '重设画框仅支持静态图像',
    'The active Image Empty is not a Frame source': '活动图像空物体不在重设画框来源中',
    'Frame does not overlap the active Image Empty': '画框区域与活动图像空物体没有重叠',
    'The selected Image Empties changed during Frame': '选中的图像空物体在重设画框期间发生了变化',
    'Maximum Frame Resolution': '画框分辨率上限',
    "Set the maximum length, in pixels, of the combined image's longest edge.": '设置合成图像最长边的像素数上限。',
    'Draw a rectangle to combine selected images into one image from the current view.': '绘制矩形，将选中的图像按当前视角合成为一张图像。',
    'Draw Frame': '拖出画框',
    'Choose Shape': '选择形状',
    'Add Point': '添加顶点',
    'Remove Point': '移除顶点',
    'Apply Mask': '应用遮罩',
    'Place Corner {index}/4': '放置角点 {index}/4',
    'Snap to Preset': '吸附到预设比例',
    'Frame Images': '重设画框',
}


# 透视校正
RECTIFY = {
    'Rectify Image Perspective': '校正图像透视',
    'Rectify only supports a still image': '透视校正仅支持静态图像',
    'Rectify quad does not overlap the source image': '校正区域与原图没有重叠',
    'Rectify': '透视校正',
    'Select four corners of an image area to correct its perspective into a rectangle.': '选择图像区域的四个角，将其透视校正为矩形。',
}


# 局部显隐
MASK = {
    'Edit Image Alpha': '编辑图像透明度',
    'Mask\u200b': '局部显隐',
    'Shape used to edit image Alpha': '用于编辑图像透明度的形状',
    'Mode': '模式',
    'Choose how the selected or painted area changes image visibility.': '选择选区或涂绘区域如何改变图像的可见性。',
    'Radius': '半径',
    'Brush radius in Viewport pixels': '画笔半径，以视口像素为单位',
    'Set': '设定',
    'Extend': '扩展',
    'Subtract': '减去',
    'Keep visible content inside the selected or painted area and hide everything outside.': '保留选区或涂绘区域内的可见内容，隐藏区域外的所有内容。',
    'Reveal the selected or painted area while keeping other areas unchanged.': '显示选区或涂绘区域，其他区域保持不变。',
    'Hide the selected or painted area while keeping other areas unchanged.': '隐藏选区或涂绘区域，其他区域保持不变。',
    'Hide or reveal image areas with a lasso, brush, or polyline.': '使用套索、画笔或折线隐藏或显示图像区域。',
}


# 立体裁切
CUTOUT = {
    'Start Cutout Selection': '开始立体裁切选区',
    'Effective Edge Length: {length}': '实际边长：{length}',
    'Minimum Relative Edge Length': '最小相对边长',
    "Minimum target edge length as a percentage of the Cutout bounds' longest side": '最小目标边长占立体裁切区域包围框最长边的百分比',
    'Boundary Padding': '边界扩展',
    'Sample inward and extend Cutout image data at the outline': '向内采样并在立体裁切轮廓处扩展图像数据',
    'Balloon Profile': '体块鼓起算法',
    'Control how the Cutout surface bulges outward from its outline.': '控制立体裁切表面从轮廓向外鼓起的形状。',
    'Create a smooth, rounded bulge within the Cutout outline.': '在立体裁切轮廓内生成平滑圆润的鼓起表面。',
    "Create a bulge shaped by the Cutout's central branches.": '根据立体裁切区域的中心分支生成鼓起表面。',
    'Shape used to select the Cutout area': '用于选择立体裁切区域的形状',
    'Alpha Threshold': '透明度阈值',
    'Fine Outline': '精细轮廓',
    'Preserve detailed outlines and meaningful holes; disable to fill holes and simplify outlines': '保留轮廓细节和有效孔洞；关闭后填充孔洞并简化轮廓',
    'Edge Length': '边长',
    'Target mesh edge length in world space': '世界空间中的目标网格边长',
    'Cutout': '立体裁切',
    'Select an Image Empty area with a lasso or polyline and choose a mesh shape': '使用套索或折线选择图像空物体的区域，并选择网格形状',
    'Cutout Shape': '立体裁切形状',
    'Flat': '面片',
    'Solid': '体块',
    'Cutout Selection to Shape': '将立体裁切选区转换为形状',
    'Select an Image Empty area with a lasso or polyline, then choose its mesh shape': '使用套索或折线选择图像空物体的区域，然后选择网格形状',
    'Exclude areas below this opacity from the Cutout outline. Higher values exclude more semi-transparent edges.': '从立体裁切轮廓中排除不透明度低于此值的区域。值越高，排除的半透明边缘越多。',
}


# 面片转换与烘焙
GEOMETRY = {
    'Bake Mesh': '烘焙网格',
    'Apply the image geometry and materialize static textures and normals': '应用图像几何体并生成静态纹理和法线',
    'Panorama input cropped from {width} x {height} to {crop_width} x {crop_height}': '全景输入已从 {width} x {height} 裁剪为 {crop_width} x {crop_height}',
    'Panorama conversion requires an image at least 2 x 1 pixels': '全景转换需要至少 2 x 1 像素的图像',
    'Convert to World': '转为世界环境',
    'Use the Image Empty as the scene environment': '将图像空物体用作场景的世界环境',
    'Convert to Plane': '转为面片',
    'Convert the complete Image Empty into a rectangular plane': '将完整的图像空物体转换为矩形平面',
}


def build_translations(*groups):
    """Build a Blender translation catalog from the selected message groups."""
    return {
        "zh_HANS": {
            (context, text): translation
            for group in groups
            for text, translation in group.items()
            for context in ("*", "Operator", "AnyImage")
        },
    }
