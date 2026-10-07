/**
 * 首页的扩展安装按钮：按系统只留一个平台，并把下载地址拖进 Blender。
 */
const INSTALL_PLATFORMS = { win: "windows", mac: "macos", lin: "linux" };

function initInstallDrag() {
  const container = document.querySelector(".anyimage-install");

  if (!container) {
    return;
  }

  // navigator.platform 的取值由浏览器决定，只取前三个字符做粗略匹配。
  const detectedPlatform = INSTALL_PLATFORMS[navigator.platform.toLowerCase().slice(0, 3)];

  container.querySelectorAll(".anyimage-install-item").forEach(function (item) {
    const matches = !detectedPlatform || item.dataset.platform.startsWith(detectedPlatform);
    item.classList.toggle("is-active", matches);
    item.hidden = !matches;
  });

  container.querySelectorAll(".anyimage-install-button").forEach(function (button) {
    const group = button.closest(".anyimage-install-group");

    button.addEventListener("dragstart", function (event) {
      event.dataTransfer.setData("text/plain", button.dataset.installUrl);
      event.dataTransfer.effectAllowed = "copy";
      group.classList.add("is-dragging");
    });

    button.addEventListener("dragend", function () {
      group.classList.remove("is-dragging");
    });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initInstallDrag);
} else {
  initInstallDrag();
}
