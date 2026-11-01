"""Translations for AI-only workflows; the full edition combines both catalogs."""


# 服务器与运行环境
ENVIRONMENT = {
    'AI Server': 'AI 服务器',
    'Danger Zone': '危险操作',
    'Set Up AI Server': '设置 AI 服务器',
    'Install the environment and required AI models': '安装运行环境和所需的 AI 模型',
    'Open the AnyImage add-on preferences': '打开「任意图！」插件偏好设置',
    'Server Root Folder': '服务器根目录',
    'Choose where AnyImage stores its AI environment, downloaded models, and job files.': '选择「任意图！」存放 AI 环境、已下载模型和任务文件的位置。',
    'Choose a Server Location': '请选择服务器位置',
    'Choose a location with a regular .anyimage directory': '请选择包含普通 .anyimage 目录的位置',
    'Choose .anyimage, a folder inside it, or a parent folder for a new installation': '选择 .anyimage 文件夹、其内部文件夹，或用于新安装的父文件夹',
    'Download Python and packages from China mirrors': '从中国镜像下载 Python 和依赖包',
    'Continue': '继续',
    'Set up AI features for depth, background removal and upscaling.': '设置深度生成、背景移除和2倍高清等 AI 功能。',
    'Use existing AI Server installation.': '使用现有的 AI 服务器安装。',
    'Starting Environment': '运行环境启动中',
    'AI environment installed.': 'AI 环境已安装。',
    'Install the AnyImage Environment first': '请先安装「任意图！」运行环境',
    'Online Access is disabled in Blender Preferences': 'Blender 偏好设置中已禁用网络访问',
    'Downloads the runtime and required models ({size} for models).': '下载运行环境和所需模型（模型共 {size}）。',
    '{size} · Usually 2–10 minutes.': '{size} · 通常需要 2–10 分钟。',
}


# 模型管理
MODELS = {
    'Models Loaded': '已加载 AI 模型',
    'Download Required Models': '下载所需模型',
    'Download Model': '下载模型',
    'Download Again': '重新下载',
    'Download': '下载',
    'Installed': '已安装',
    'Validation failed': '校验失败',
    '{label} (Installed)': '{label}（已安装）',
    'Unload': '卸载',
    'Unload Models': '卸载模型',
    'Free memory used by AI models to keep viewport and rendering responsive': '释放 AI 模型占用的内存，保持视口和渲染流畅',
    'Starting required model downloads': '所需模型下载启动中',
    'Required models are ready': '所需模型已就绪',
    'Downloading {item}': '{item} 下载中',
    'Downloading {item} {rate}': '{item} 下载中 {rate}',
    'Downloading {item} (mirror)': '{item} 下载中（镜像）',
    'Downloading {item} (mirror) {rate}': '{item} 下载中（镜像） {rate}',
    'Loading {model}': '{model} 加载中',
    '{model} ready': '{model} 已就绪',
    'Download: {models}': '下载：{models}',
    '{description}; license: {license}': '{description}；许可证：{license}',
    'Starting model download': '模型下载启动中',
}


# 处理设置
PROCESSING = {
    'AI Processing Device': 'AI 运算设备',
    'Choose the CPU or GPU used to run AI models.': '选择运行 AI 模型的 CPU 或 GPU。',
    'Maximum AI Input Size': '处理分辨率上限',
    'Limit the longest image edge used for depth, normal, and selection refinement. Upscale requires a source image smaller than this limit.': '限制深度、法线生成和选区优化时的图像最长边。2倍高清功能要求原图尺寸小于此上限。',
    'Image long edge must be smaller than Maximum AI Input Size ({size} px)': '图像最长边必须小于处理分辨率上限（{size} 像素）',
    '{job}  [ {tier} ]': '{job}  [ {tier} ]',
}


# 深度与法线
GEOMETRY = {
    'Generate Plane Geometry': '生成面片几何',
    'Depth & Normal Model': '深度与法线模型',
    'Choose the AI model used to generate depth and surface normals.': '选择用于生成深度和表面法线的 AI 模型。',
    'Generate depth and surface normals with the fastest MoGe-2 option.': '使用速度最快的 MoGe-2 模型生成深度和表面法线。',
    'Generate depth and surface normals with a balance of processing speed and detail.': '兼顾处理速度和细节，生成深度和表面法线。',
    'Generate depth and surface normals with MoGe-3, refining the prediction in three steps.': '使用 MoGe-3 生成深度和表面法线，通过三个步骤细化预测结果。',
    'MoGe Resolution Level': 'MoGe 分辨率级别',
    'Set the processing resolution for depth and normal generation. Higher levels can capture finer details but take more time and memory.': '设置生成深度和法线的处理分辨率。级别越高，细节越丰富，但耗时和内存占用也越多。',
    'Normal Map': '法线贴图',
    'Generate a normal map to add surface detail under lighting for Flat and Solid shapes. Depth Solid and Depth Symmetry always generate normal maps.': '为面片和体块生成法线贴图，增加光照下的表面细节。凹凸体块和对称凹凸始终生成法线贴图。',
    'Convert to Depth Plane': '转为凹凸面',
    "Use AI-estimated depth to turn the image into a 3D surface that follows the source image's perspective.": '使用 AI 估计的深度，将图像转换为符合原图透视的三维表面。',
    'Convert to Relief': '转为浮雕',
    'Use AI-estimated depth to create a raised relief on a flat base.': '使用 AI 估计的深度，在平坦底面上创建凸起的浮雕。',
    'Depth Symmetry': '对称凹凸',
    'Depth Solid': '凹凸体块',
    'Preparing depth conversion': '深度转换准备中',
    'Generating depth texture': '深度纹理生成中',
    'Generating surface normal': '表面法线生成中',
    'Depth conversion data is ready': '深度转换数据已就绪',
    'Depth Plane is ready': '凹凸面已就绪',
    'Relief is ready': '浮雕已就绪',
    'Flat is ready': '面片已就绪',
    'Solid is ready': '体块已就绪',
    'Depth Symmetry is ready': '对称凹凸已就绪',
    'Depth Solid is ready': '凹凸体块已就绪',
}


# 全景
PANORAMA = {
    'Generate Panorama': '生成全景',
    'Convert to Panorama': '转为立体全景',
    'Turn a still panoramic image into a surrounding 3D surface using AI-estimated depth.': '使用 AI 估计的深度，将静态全景图像转换为环绕的三维表面。',
    'Panorama conversion requires a static image': '全景转换需要静态图像',
    'Not enough memory to prepare the HDR image': '内存不足，无法准备 HDR 图像',
    'Panorama input cropped from {width} x {height} to {crop_width} x {crop_height}': '全景输入已从 {width} x {height} 裁剪为 {crop_width} x {crop_height}',
    'Preparing panorama conversion': '全景转换准备中',
    'Generating panorama view {index}/{total}': '全景视角生成中 {index}/{total}',
    'Merging panorama depth maps': '全景深度图合并中',
    'Merging panorama normal maps': '全景法线图合并中',
    'Panorama conversion data is ready': '全景转换数据已就绪',
    'Panorama is ready': '全景已就绪',
}


# 图像放大
UPSCALE = {
    'Upscale Image Model': '2倍高清模型',
    'Model used to upscale images': '用于生成2倍高清图像的模型',
    'Enlarge images to twice their width and height with fast, restrained detail enhancement.': '将图像的宽高放大至两倍，快速、适度地增强细节。',
    'Enlarge images to twice their width and height with stronger detail enhancement.': '将图像的宽高放大至两倍，更明显地增强细节。',
    'Enlarge images to twice their width and height with detailed texture enhancement. Requires more processing time.': '将图像的宽高放大至两倍，增强纹理细节。需要更长的处理时间。',
    'AI Upscale Image': 'AI 2倍高清',
    'Upscale Image': '2倍高清',
    'Upscale': '2倍高清',
    'Upscale the image by 2x with an AI model': '使用 AI 模型生成2倍高清图像',
    'Max AI Input Size': '处理分辨率上限',
    'Maximum input long edge used for AI upscale analysis': '用于 AI 2倍高清分析的输入图像最长边上限',
    'Upscale ({width} × {height})': '2倍高清（{width} × {height}）',
    'Starting image upscale': '2倍高清启动中',
    'Preparing upscale input': '2倍高清输入图像准备中',
    'Upscaling image': '2倍高清图像生成中',
    'Image upscale complete': '2倍高清已完成',
    'Image is upscaled with {model}': '已使用 {model} 生成2倍高清图像',
}


# 背景移除
BACKGROUND_REMOVAL = {
    'Remove Background Model': '背景移除模型',
    'Model used to remove image backgrounds': '用于移除图像背景的模型',
    'Remove backgrounds at 1024 px processing resolution while preserving soft, semi-transparent edges.': '以 1024 像素处理分辨率移除背景，保留柔和的半透明边缘。',
    'Remove backgrounds from general images while preserving foreground transparency.': '移除普通图像的背景，保留前景透明度。',
    'Remove backgrounds at 2048 px processing resolution while preserving soft, semi-transparent edges. Runs on CPU and requires more time and memory.': '以 2048 像素处理分辨率移除背景，保留柔和的半透明边缘。在 CPU 上运行，需要更多时间和内存。',
    'AI Remove Background': 'AI 移除背景',
    'Remove Background': '移除背景',
    'Remove the image background with the selected AI model': '使用所选 AI 模型移除图像背景',
    'Run Background Removal': '执行背景移除',
    'Starting image background removal': '背景移除启动中',
    'Removing background': '背景移除中',
    'Writing transparent PNG': '透明 PNG 写入中',
    'Image background is removed': '图像背景已移除',
    'Background removed in {inference} ms (model load {load} ms, total {total} ms)': '背景移除耗时 {inference} 毫秒（模型加载 {load} 毫秒，总计 {total} 毫秒）',
}


# 立体裁切
CUTOUT = {
    'Build the image selection as a Cutout shape': '将图像选区构建为立体裁切形状',
    'Preparing Cutout Selection': '立体裁切选区准备中',
    'Generating Cutout artifacts': '立体裁切数据生成中',
    'Cutout artifacts are ready': '立体裁切数据已就绪',
    'The normal texture is missing; the shape was created without it': '缺少法线贴图，已继续生成物体',
}


TRANSLATIONS = {
    "zh_HANS": {
        (context, text): translation
        for group in (
            ENVIRONMENT,
            MODELS,
            PROCESSING,
            GEOMETRY,
            PANORAMA,
            UPSCALE,
            BACKGROUND_REMOVAL,
            CUTOUT,
        )
        for text, translation in group.items()
        for context in ("*", "Operator", "AnyImage")
    },
}
