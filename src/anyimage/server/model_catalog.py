from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    directory_name: str
    repository: str
    license_name: str
    description: str
    family: str
    adapter: str
    device: str = ""
    tile_border: int = 16
    huggingface_repository: str = ""
    r2_directory: str = ""
    files: tuple[tuple[str, int, str], ...] = ()


BIREFNET_LITE = ModelSpec(
    key="BIREFNET_LITE",
    family="background",
    adapter="onnx_birefnet",
    label="BiRefNet Lite",
    directory_name="birefnet-lite",
    repository="ZhengPeng7/BiRefNet_lite",
    license_name="MIT",
    description="Remove backgrounds at 1024 px processing resolution while preserving soft, semi-transparent edges.",
    r2_directory="birefnet-lite",
    files=(
        ("model.onnx", 112968598, "6e2a9844c57b080e95a402722ddcae5660e6f254a04d3e003347f06f587b71fe"),
        ("LICENSE.txt", 1066, "92a7089e0915fc32bc40067560b398f1e6a7a5958abd7d04eda393629a5acefb"),
    ),
)


BEN2_MODEL = ModelSpec(
    key="BEN2_BASE",
    family="background",
    adapter="onnx_ben2",
    label="BEN2 Base",
    directory_name="BEN2-ONNX",
    repository="onnx-community/BEN2-ONNX",
    license_name="Apache 2.0",
    huggingface_repository="onnx-community/BEN2-ONNX",
    description="Remove backgrounds from general images while preserving foreground transparency.",
    r2_directory="BEN2-ONNX",
    files=((
        "onnx/model_fp16.onnx",
        219121675,
        "dfdc25f421f32a0d1268e0f2ff2153d340e8f1d52d3dd16f5dc33c1ce85cedf1",
    ),),
)


REALESRGAN_GENERAL_WDN_X4V3 = ModelSpec(
    key="REALESRGAN_GENERAL_WDN_X4V3",
    family="upscale",
    adapter="onnx_upscale",
    label="Real-ESRGAN General WDN x4v3",
    directory_name="realesr-general-wdn-x4v3",
    repository="xinntao/Real-ESRGAN",
    license_name="BSD 3-Clause",
    description="Enlarge images to twice their width and height with fast, restrained detail enhancement.",
    r2_directory="realesr-general-wdn-x4v3",
    files=((
        "realesr-general-wdn-x4v3.onnx",
        4867419,
        "b021a837f7a0d3f287f9a39e367f581f1e6c3a759a08dc0c1c79c22442729774",
    ),),
)


REALESRGAN_X4PLUS = ModelSpec(
    key="REALESRGAN_X4PLUS",
    family="upscale",
    adapter="onnx_upscale",
    label="Real-ESRGAN x4plus",
    directory_name="realesrgan-x4plus",
    repository="jonathanst29/tinier-upscale-models",
    license_name="BSD 3-Clause",
    huggingface_repository="jonathanst29/tinier-upscale-models",
    description="Enlarge images to twice their width and height with stronger detail enhancement.",
    r2_directory="realesrgan-x4plus",
    files=((
        "realesrgan-x4plus.onnx",
        67051618,
        "4ed6a45a8185bde6c8d7c7790a6e80e3c5b9f608946f634021068dd0fd0473c8",
    ),),
)




HAT_GAN_X4_SHARPER = ModelSpec(
    key="HAT_GAN_X4_SHARPER",
    family="upscale",
    adapter="onnx_upscale",
    tile_border=48,
    label="HAT Sharper",
    directory_name="hat-gan-x4-sharper",
    repository="XPixelGroup/HAT",
    license_name="Apache 2.0",
    description=(
        "Enlarge images to twice their width and height with detailed texture enhancement. "
        "Requires more processing time."
    ),
    r2_directory="hat-gan-x4-sharper",
    files=(
        ("model.onnx", 45874438, "032d8b03c704220a08d91465a822aca252c1d6e63db20c3cf23c5fb67f3d2366"),
        ("LICENSE.txt", 11342, "a91d57ebad8955a1757be7891ca2da8e07493e662f0e34e1e1926571e05f37fc"),
    ),
)


UPSCALE_MODELS = {
    model.key: model
    for model in (
        REALESRGAN_GENERAL_WDN_X4V3,
        REALESRGAN_X4PLUS,
        HAT_GAN_X4_SHARPER,
    )
}


DEFAULT_UPSCALE_MODEL_KEY = REALESRGAN_GENERAL_WDN_X4V3.key


MOGE2_MODELS = {
    "MOGE2_VITS_NORMAL": ModelSpec(
        key="MOGE2_VITS_NORMAL",
        family="moge",
        adapter="onnx_moge2",
        label="MoGe-2 ViT-S Normal",
        directory_name="moge-2-vits-normal-onnx",
        repository="Ruicheng/moge-2-vits-normal-onnx",
        license_name="MIT",
        huggingface_repository="Ruicheng/moge-2-vits-normal-onnx",
        description="Generate depth and surface normals with the fastest MoGe-2 option.",
        r2_directory="moge-2-vits-normal-onnx",
        files=((
            "model.onnx",
            140852051,
            "24eacb5dc7a2c54c7bc98f7de085ffbed79ad006ea5b664c2c2cdc02ff3a52f0",
        ),),
    ),
    "MOGE2_VITB_NORMAL": ModelSpec(
        key="MOGE2_VITB_NORMAL",
        family="moge",
        adapter="onnx_moge2",
        label="MoGe-2 ViT-B Normal",
        directory_name="moge-2-vitb-normal-onnx",
        repository="Ruicheng/moge-2-vitb-normal-onnx",
        license_name="MIT",
        huggingface_repository="Ruicheng/moge-2-vitb-normal-onnx",
        description="Generate depth and surface normals with a balance of processing speed and detail.",
        r2_directory="moge-2-vitb-normal-onnx",
        files=((
            "model.onnx",
            419411850,
            "bbf14e07a30f11e69d36ab861590123f5598ababcbc8946a063eb4a966f35a21",
        ),),
    ),
}
MOGE3_VITL = ModelSpec(
    key="MOGE3_VITL",
    family="moge",
    adapter="onnx_moge3",
    label="MoGe-3 ViT-L",
    directory_name="moge-3-vitl-onnx",
    repository="Ruicheng/moge-3-vitl",
    license_name="MIT",
    description="Generate depth and surface normals with MoGe-3, refining the prediction in three steps.",
    r2_directory="moge-3-vitl-onnx",
    files=(
        ("backbone.onnx", 1324190318, "f21246c6921373c8c79ecdb8c78818a79bd2506c2fb88f4d4cdec21b92f725e3"),
        ("refiner.onnx", 157729628, "67ad7297aba18f8ef7939e8f700a5b25c41a19ddb68656bc2cd08b54c248fe2a"),
    ),
)

MOGE_MODELS = {**MOGE2_MODELS, MOGE3_VITL.key: MOGE3_VITL}
BIREFNET_HR_MATTING = ModelSpec(
    key="BIREFNET_HR_MATTING",
    family="background",
    adapter="onnx_birefnet",
    device="cpu",
    label="BiRefNet HR-matting (CPU)",
    directory_name="birefnet-hr-matting",
    repository="ZhengPeng7/BiRefNet_HR-matting",
    license_name="MIT",
    description=(
        "Remove backgrounds at 2048 px processing resolution while preserving soft, semi-transparent edges. "
        "Runs on CPU and requires more time and memory."
    ),
    r2_directory="birefnet-hr-matting",
    files=(
        ("model.onnx", 529467341, "b3abc34843a4d96f669ca9fb1a2a16b3417ab8b91c987573fdbda36d20514133"),
        ("LICENSE.txt", 1066, "92a7089e0915fc32bc40067560b398f1e6a7a5958abd7d04eda393629a5acefb"),
    ),
)

BACKGROUND_MODELS = {model.key: model for model in (BIREFNET_LITE, BEN2_MODEL, BIREFNET_HR_MATTING)}
DEFAULT_GEOMETRY_MODEL_KEY = next(iter(MOGE_MODELS))
DEFAULT_BACKGROUND_MODEL_KEY = next(iter(BACKGROUND_MODELS))
DEFAULT_MODEL_KEYS = (
    DEFAULT_GEOMETRY_MODEL_KEY,
    DEFAULT_BACKGROUND_MODEL_KEY,
    DEFAULT_UPSCALE_MODEL_KEY,
)

DOWNLOADABLE_MODELS = {
    **BACKGROUND_MODELS,
    **UPSCALE_MODELS,
    **MOGE_MODELS,
}


def get_downloadable_model(model_key):
    try:
        return DOWNLOADABLE_MODELS[model_key]
    except KeyError as error:
        raise ValueError(f"Unknown model: {model_key}") from error


def model_record(model, ready=False):
    """Return public model metadata exposed by the Models Resource."""
    return {
        "key": model.key,
        "label": model.label,
        "description": model.description,
        "license": model.license_name,
        "family": model.family,
        "ready": bool(ready),
    }
