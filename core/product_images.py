"""只读本地图片校验；缩略图与排序仅保存在内存。"""
from dataclasses import dataclass
from io import BytesIO
import logging
from pathlib import Path, PureWindowsPath
import re
import warnings
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)
FORMATS = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP'}
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000

@dataclass(frozen=True)
class ProductImage:
    path: Path
    width: int
    height: int
    byte_size: int
    thumbnail: bytes

@dataclass
class ImageCollection:
    images: list[ProductImage]
    errors: list[str]
    main: Path | None = None

    def set_main(self, index: int) -> None:
        self.main = self.images[index].path

    def move(self, index: int, target: int) -> None:
        if not 0 <= index < len(self.images) or not 0 <= target < len(self.images):
            raise IndexError('图片顺序索引越界')
        self.images.insert(target, self.images.pop(index))


def natural_key(path: Path) -> tuple:
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold()) for part in re.split(r'(\d+)', path.name))


def scan_images(root: Path, image_folder: str) -> ImageCollection:
    """匹配根目录下的相对文件夹，拒绝绝对路径、遍历和所有符号链接。"""
    result = ImageCollection([], [])
    try:
        root = Path(root).resolve(strict=True)
        text = image_folder.replace('\\', '/')
        relative = Path(text)
        if not text.strip() or relative.is_absolute() or PureWindowsPath(text).drive or '..' in relative.parts:
            raise ValueError('image_folder 必须为根目录内的相对路径，禁止 .. 或绝对路径')
        folder = root / relative
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError('禁止通过符号链接读取图片目录')
        folder = folder.resolve(strict=True)
        if not folder.is_relative_to(root) or not folder.is_dir():
            raise ValueError('图片目录不在根目录内或不是目录')
        for path in sorted(folder.iterdir(), key=natural_key):
            if path.is_dir() and not path.is_symlink():
                continue
            try:
                if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
                    raise ValueError('禁止符号链接或根目录外的文件')
                if not path.is_file():
                    raise ValueError('不是普通文件')
                expected = FORMATS.get(path.suffix.lower())
                if expected is None:
                    raise ValueError('不支持的图片扩展名，仅支持 JPG/JPEG/PNG/WEBP')
                size = path.stat().st_size
                if not 0 < size <= MAX_BYTES:
                    raise ValueError('图片为空或超过 20 MiB')
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(path) as image:
                        if image.format != expected:
                            raise ValueError(f'实际格式 {image.format} 与扩展名不匹配')
                        width, height = image.size
                        if width * height > MAX_PIXELS:
                            raise ValueError('图片超过 4000 万像素')
                        image.verify()
                    with Image.open(path) as image:
                        image.load()
                        thumb = ImageOps.exif_transpose(image).convert('RGB')
                        thumb.thumbnail((640, 640))
                        stream = BytesIO()
                        thumb.save(stream, format='PNG')
                result.images.append(ProductImage(path, width, height, size, stream.getvalue()))
            except Exception as exc:
                logger.warning('图片校验失败 %s: %s', path.name, exc)
                result.errors.append(f'{path.name}：{type(exc).__name__}: {exc}')
        if not result.images:
            result.errors.append('没有可用图片')
        else:
            result.main = result.images[0].path
    except Exception as exc:
        logger.warning('图片目录校验失败: %s', exc)
        result.errors.append(f'image_folder：{type(exc).__name__}: {exc}')
    return result
