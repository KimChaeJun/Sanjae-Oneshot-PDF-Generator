import base64
import binascii
import io

from PIL import Image, UnidentifiedImageError


def decode_signature(value: str) -> bytes:
    prefix = "data:image/png;base64,"
    if not value.startswith(prefix) or len(value) > 400_000:
        raise ValueError("서명은 300KB 이하의 PNG 이미지여야 합니다.")
    try:
        payload = base64.b64decode(value[len(prefix):], validate=True)
        with Image.open(io.BytesIO(payload)) as image:
            if image.format != "PNG" or image.mode not in {"RGBA", "LA"} or image.width > 1920 or image.height > 560:
                raise ValueError("투명 배경의 시연용 서명 PNG가 필요합니다.")
            image.verify()
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("서명 이미지가 올바르지 않습니다.") from exc
    return payload
