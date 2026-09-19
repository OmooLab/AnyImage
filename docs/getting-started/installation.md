# 安装与首次配置

页面会按当前系统显示对应的安装包，按住按钮拖到 Blender 窗口任意位置即可安装。首次拖入会提示添加 AnyImage 扩展仓库，确认后重新拖入一次，之后升级同样直接拖入。

<div class="anyimage-install">
  <div class="anyimage-install-item" data-platform="windows-x64">
    <div class="anyimage-install-group">
      <button type="button" draggable="true" class="anyimage-install-button" data-install-url="https://extensions.omoolab.xyz/AnyImage.v1.0.1.windows-x64.zip?repository=.%2Findex.json&amp;blender_version_min=4.5.0&amp;platforms=windows-x64&amp;python_versions=3.11%2C3.13">
        <i class="i-move"></i><span>拖入 Blender 安装</span>
      </button>
      <div class="anyimage-install-platform"><strong>Windows</strong> – 78.3&nbsp;MB</div>
    </div>
    <small class="anyimage-install-note">…或<a href="https://extensions.omoolab.xyz/AnyImage.v1.0.1.windows-x64.zip" download="AnyImage.v1.0.1.windows-x64.zip">下载</a>后通过 <a href="https://docs.blender.org/manual/zh-hans/latest/editors/preferences/extensions.html#install" target="_blank">Install from Disk</a> 安装</small>
  </div>
  <div class="anyimage-install-item" data-platform="macos-arm64">
    <div class="anyimage-install-group">
      <button type="button" draggable="true" class="anyimage-install-button" data-install-url="https://extensions.omoolab.xyz/AnyImage.v1.0.1.macos-arm64.zip?repository=.%2Findex.json&amp;blender_version_min=4.5.0&amp;platforms=macos-arm64&amp;python_versions=3.11%2C3.13">
        <i class="i-move"></i><span>拖入 Blender 安装</span>
      </button>
      <div class="anyimage-install-platform"><strong>macOS<span class="anyimage-install-platform-rest"> - Apple Silicon</span></strong> – 57.5&nbsp;MB</div>
    </div>
    <small class="anyimage-install-note">…或<a href="https://extensions.omoolab.xyz/AnyImage.v1.0.1.macos-arm64.zip" download="AnyImage.v1.0.1.macos-arm64.zip">下载</a>后通过 <a href="https://docs.blender.org/manual/zh-hans/latest/editors/preferences/extensions.html#install" target="_blank">Install from Disk</a> 安装</small>
  </div>
  <div class="anyimage-install-item" data-platform="linux-x64">
    <div class="anyimage-install-group">
      <button type="button" draggable="true" class="anyimage-install-button" data-install-url="https://extensions.omoolab.xyz/AnyImage.v1.0.1.linux-x64.zip?repository=.%2Findex.json&amp;blender_version_min=4.5.0&amp;platforms=linux-x64&amp;python_versions=3.11%2C3.13">
        <i class="i-move"></i><span>拖入 Blender 安装</span>
      </button>
      <div class="anyimage-install-platform"><strong>Linux</strong> – 71.0&nbsp;MB</div>
    </div>
    <small class="anyimage-install-note">…或<a href="https://extensions.omoolab.xyz/AnyImage.v1.0.1.linux-x64.zip" download="AnyImage.v1.0.1.linux-x64.zip">下载</a>后通过 <a href="https://docs.blender.org/manual/zh-hans/latest/editors/preferences/extensions.html#install" target="_blank">Install from Disk</a> 安装</small>
  </div>
</div>

## 检查扩展偏好设置

AnyImage 的扩展偏好设置按功能分组。Environment 区包含：

- **Storage Root**：保存运行环境、模型和任务文件的位置。默认是用户目录下的 `.anyimage`，一般无需修改。
- **Device**：正式转换任务使用的计算设备。Apple Silicon Mac 默认使用 CPU，Windows 默认使用 DirectML；也可手动选择其他可用设备。

macOS arm64 提供 **CPU** 与 **CoreML**。CoreML 由系统在 Apple CPU、GPU 与 Neural Engine 之间调度，不是 PyTorch MPS backend，也不表示只使用 GPU；它的实际速度取决于模型。

Environment 检测后显示 Diagnostics。Depth & Normal、Remove Background、Upscale 与 Cutout 是默认展开的可折叠功能区，各自包含对应设置和模型状态。其中：

- **Default Upscale Model**：Upscale 使用的模型，默认是 General WDN x4v3。
- **Maximum AI Input Size**：Upscale、Depth 与 Normal Map 的 AI 输入长边上限，默认 2048 px；颜色贴图保留原始分辨率。
- **Maximum Cutout Mesh Resolution**：所有 Cutout Shape 的网格采样长边上限，默认 1024，独立于 AI 输入尺寸。

Depth & Normal 提供三档 MoGe-2，Depth Plane 与 Cutout Depth / Normal Map 共用当前选择。可选模型的 **Ready** 状态或 **Download** 按钮位于选择项下方；Cutout 区提供独立网格上限与 Balloon Profile。

如果准备把 Storage Root 放到其他磁盘，建议在首次安装 Environment 之前修改。更换目录后，旧目录中的环境和模型不会自动移动。

## 配置 AI Environment

选中 Image Empty，在右键 **AnyImage** 子菜单中点击 **Set Up AI Environment…**；也可以在 AnyImage 扩展偏好设置中点击同名按钮。

确认安装前，对话框会说明以下内容：

- 安装独立 Python、ONNX Runtime 与支持包，并下载 **MoGe-2 ViT-S Normal**、**BEN2 Base** 和 **Real-ESRGAN General WDN x4v3**。
- 默认模型合计约 360 MB；连同 Environment 预计需要约 600 MB 下载量和约 1 GB 磁盘空间。
- 根据网络速度，首次安装通常需要 5–20 分钟。
- **Use Mirror** 只让 uv、Python 和 Python 包使用国内镜像；模型下载源保持不变。

安装过程中请保持 Blender 打开。状态栏会显示当前阶段、进度和下载速度。

如果 Environment 已安装但任一默认模型缺失，入口会改为 **Download Required Models…**；对话框列出缺失模型和下载体积，确认后只下载缺失模型，不会重装 Environment 或重复下载已就绪内容。

## 确认安装完成

完成后可以用以下方式确认：

- AnyImage 扩展偏好设置中的 MoGe-2 ViT-S Normal、BEN2 Base 和 Real-ESRGAN General WDN x4v3 显示 **Ready**。
- 选中 Image Empty 后，右键菜单底部显示 **AI Environment Settings…**。

点击 **Convert to Depth Plane**、**Remove Background** 或 **Upscale** 时，AnyImage 会根据状态进入 **Set Up AI Environment…** 或 **Download Required Models…**。普通 Plane、Image 编辑和基础 Cutout Surface / Balloon 直接在 Blender 中执行。

## 下一步

继续阅读[五分钟上手](quick-start.md)，用一张图片完成第一次转换。
