import ctypes
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path


CF_DIB = 8
CF_DIBV5 = 17
MAX_CLIPBOARD_IMAGE_SIZE = 512 * 1024 * 1024
CLIPBOARD_COMMAND_TIMEOUT = 10
LINUX_IMAGE_FORMATS = (
    ("image/png", ".png"),
    ("image/jpeg", ".jpg"),
    ("image/tiff", ".tiff"),
    ("image/bmp", ".bmp"),
)


class ClipboardImageError(RuntimeError):
    pass


class ClipboardImageUnavailable(ClipboardImageError):
    pass


def dib_to_bmp(dib_data):
    if len(dib_data) < 12:
        raise ClipboardImageError("Clipboard DIB data is incomplete")

    header_size = struct.unpack_from("<I", dib_data)[0]
    if header_size == 12:
        pixel_offset = _core_dib_pixel_offset(dib_data)
    elif header_size >= 40:
        pixel_offset = _info_dib_pixel_offset(dib_data, header_size)
    else:
        raise ClipboardImageError(
            f"Unsupported clipboard DIB header size: {header_size}"
        )

    # Windows 剪贴板保存的是无 BITMAPFILEHEADER 的 DIB，Blender 需要完整 BMP。
    file_size = 14 + len(dib_data)
    file_header = struct.pack(
        "<2sIHHI",
        b"BM",
        file_size,
        0,
        0,
        14 + pixel_offset,
    )
    return file_header + dib_data


def _core_dib_pixel_offset(dib_data):
    if len(dib_data) < 12:
        raise ClipboardImageError("Clipboard DIB core header is incomplete")

    bit_count = struct.unpack_from("<H", dib_data, 10)[0]
    color_count = 1 << bit_count if bit_count <= 8 else 0
    pixel_offset = 12 + color_count * 3
    _validate_pixel_offset(dib_data, pixel_offset)
    return pixel_offset


def _info_dib_pixel_offset(dib_data, header_size):
    if len(dib_data) < header_size or len(dib_data) < 40:
        raise ClipboardImageError("Clipboard DIB info header is incomplete")

    bit_count = struct.unpack_from("<H", dib_data, 14)[0]
    compression = struct.unpack_from("<I", dib_data, 16)[0]
    colors_used = struct.unpack_from("<I", dib_data, 32)[0]

    color_count = colors_used
    if color_count == 0 and bit_count <= 8:
        color_count = 1 << bit_count

    mask_size = 0
    if header_size == 40 and compression == 3:
        mask_size = 12
    if header_size == 40 and compression == 6:
        mask_size = 16

    pixel_offset = header_size + mask_size + color_count * 4
    if header_size >= 124:
        profile_offset = struct.unpack_from("<I", dib_data, 112)[0]
        profile_size = struct.unpack_from("<I", dib_data, 116)[0]
        if profile_offset and profile_size:
            pixel_offset = max(pixel_offset, profile_offset + profile_size)
    _validate_pixel_offset(dib_data, pixel_offset)
    return pixel_offset


def _validate_pixel_offset(dib_data, pixel_offset):
    if pixel_offset > len(dib_data):
        raise ClipboardImageError("Clipboard DIB pixel offset is out of range")


def read_clipboard_image():
    if sys.platform == "win32":
        return _read_windows_clipboard_image()
    if sys.platform == "darwin":
        return _read_macos_clipboard_image()
    if sys.platform.startswith("linux"):
        return _read_linux_clipboard_image()
    raise ClipboardImageUnavailable("Clipboard image paste is unavailable")


def clipboard_image_supported():
    return (
        sys.platform == "win32"
        or sys.platform == "darwin"
        or sys.platform.startswith("linux")
    )


def _read_windows_clipboard_image():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _configure_windows_api(user32, kernel32)

    png_format = user32.RegisterClipboardFormatW("PNG")
    formats = (
        (png_format, ".png", False),
        (CF_DIBV5, ".bmp", True),
        (CF_DIB, ".bmp", True),
    )

    if not user32.OpenClipboard(None):
        error_code = ctypes.get_last_error()
        raise ClipboardImageError(
            f"Unable to open the Windows clipboard (error {error_code})"
        )

    try:
        for clipboard_format, suffix, is_dib in formats:
            if not clipboard_format:
                continue
            if not user32.IsClipboardFormatAvailable(clipboard_format):
                continue

            image_data = _read_windows_clipboard_data(
                user32,
                kernel32,
                clipboard_format,
            )
            if is_dib:
                image_data = dib_to_bmp(image_data)
            return image_data, suffix
    finally:
        user32.CloseClipboard()

    raise ClipboardImageUnavailable("The clipboard does not contain an image")


def _read_macos_clipboard_image():
    osascript = shutil.which("osascript")
    if osascript is None:
        raise ClipboardImageError("macOS clipboard access requires osascript")

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="blender-clipboard-",
        suffix=".png",
    )
    os.close(file_descriptor)
    output_file = Path(temporary_name)
    output_file.unlink()

    try:
        _export_macos_clipboard_image(osascript, output_file)
        image_data = _read_image_file(output_file)
    finally:
        output_file.unlink(missing_ok=True)

    if image_data is None:
        raise ClipboardImageUnavailable("The clipboard does not contain an image")
    return image_data, ".png"


def _export_macos_clipboard_image(osascript, output_file):
    output_path = json.dumps(str(output_file))
    script = f"""
ObjC.import('AppKit');

const pasteboard = $.NSPasteboard.generalPasteboard;
const image = $.NSImage.alloc.initWithPasteboard(pasteboard);
if (image) {{
    const bitmap = $.NSBitmapImageRep.imageRepWithData(image.TIFFRepresentation);
    if (!bitmap) {{
        throw new Error('Unable to create a bitmap from the clipboard image');
    }}
    const png = bitmap.representationUsingTypeProperties(
        $.NSBitmapImageFileTypePNG,
        $({{}})
    );
    if (!png || !png.writeToFileAtomically($({output_path}), true)) {{
        throw new Error('Unable to export the clipboard image as PNG');
    }}
}}
"""
    try:
        result = subprocess.run(
            [osascript, "-l", "JavaScript", "-e", script],
            capture_output=True,
            check=False,
            timeout=CLIPBOARD_COMMAND_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ClipboardImageError(
            f"Unable to access the macOS clipboard: {error}"
        ) from error

    if result.returncode == 0:
        return
    error_text = result.stderr.decode(errors="replace").strip()
    raise ClipboardImageError(
        error_text or "Unable to access the macOS clipboard"
    )


def _read_linux_clipboard_image():
    commands = []
    wl_paste = shutil.which("wl-paste")
    if wl_paste is not None:
        commands.append(
            lambda mime_type: [
                wl_paste,
                "--no-newline",
                "--type",
                mime_type,
            ]
        )

    xclip = shutil.which("xclip")
    if xclip is not None:
        commands.append(
            lambda mime_type: [
                xclip,
                "-selection",
                "clipboard",
                "-t",
                mime_type,
                "-o",
            ]
        )

    for command_for_type in commands:
        for mime_type, suffix in LINUX_IMAGE_FORMATS:
            image_data = _run_image_command(
                command_for_type(mime_type),
            )
            if image_data is not None:
                return image_data, suffix

    if not commands:
        raise ClipboardImageUnavailable(
            "Install wl-clipboard or xclip to paste clipboard images on Linux"
        )
    raise ClipboardImageUnavailable("The clipboard does not contain an image")


def _run_image_command(command):
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="blender-clipboard-",
    )
    output_file = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as image_file:
            try:
                result = subprocess.run(
                    command,
                    stdout=image_file,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=CLIPBOARD_COMMAND_TIMEOUT,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise ClipboardImageError(
                    f"Unable to access the Linux clipboard: {error}"
                ) from error

        if result.returncode != 0:
            return None
        return _read_image_file(output_file)
    finally:
        output_file.unlink(missing_ok=True)


def _read_image_file(image_file):
    try:
        image_size = image_file.stat().st_size
    except FileNotFoundError:
        return None
    if image_size <= 0:
        return None
    if image_size > MAX_CLIPBOARD_IMAGE_SIZE:
        raise ClipboardImageError("Clipboard image is larger than 512 MiB")
    return image_file.read_bytes()


def _configure_windows_api(user32, kernel32):
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT

    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t


def _read_windows_clipboard_data(user32, kernel32, clipboard_format):
    data_handle = user32.GetClipboardData(clipboard_format)
    if not data_handle:
        error_code = ctypes.get_last_error()
        raise ClipboardImageError(
            f"Unable to read clipboard image data (error {error_code})"
        )

    data_size = kernel32.GlobalSize(data_handle)
    if data_size <= 0:
        raise ClipboardImageError("Clipboard image data is empty")
    if data_size > MAX_CLIPBOARD_IMAGE_SIZE:
        raise ClipboardImageError("Clipboard image is larger than 512 MiB")

    data_pointer = kernel32.GlobalLock(data_handle)
    if not data_pointer:
        error_code = ctypes.get_last_error()
        raise ClipboardImageError(
            f"Unable to lock clipboard image data (error {error_code})"
        )

    try:
        return ctypes.string_at(data_pointer, data_size)
    finally:
        kernel32.GlobalUnlock(data_handle)
