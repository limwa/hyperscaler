"""Cloud image download and cache helpers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
from urllib.parse import urlparse
from urllib.request import urlopen


@dataclass(frozen=True)
class CloudImage:
    """A downloadable cloud image artifact."""

    name: str
    url: str
    file_name: str | None = None
    sha256: str | None = None


def download_cloud_image(
    image: CloudImage,
    *,
    cache_dir: Path | None = None,
) -> Path:
    """Download a cloud image into the local cache and return its path."""

    cache = cache_dir or __default_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)

    path = cache / (image.file_name or __file_name_from_url(image.url))
    if path.exists():
        __verify_sha256(path, image.sha256)
        return path

    temporary_path = path.with_suffix(f"{path.suffix}.partial")
    with urlopen(image.url) as response, temporary_path.open("wb") as handle:
        shutil.copyfileobj(response, handle)

    temporary_path.replace(path)
    __verify_sha256(path, image.sha256)
    return path


def __default_cache_dir() -> Path:
    explicit_cache = os.environ.get("HYPERSCALER_IMAGE_CACHE")
    if explicit_cache:
        return Path(explicit_cache).expanduser()

    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "hyperscaler" / "images"

    return Path.home() / ".cache" / "hyperscaler" / "images"


def __file_name_from_url(url: str) -> str:
    path = urlparse(url).path
    name = Path(path).name
    if not name:
        raise ValueError(f"cannot derive file name from URL: {url}")
    return name


def __verify_sha256(path: Path, expected_sha256: str | None) -> None:
    if expected_sha256 is None:
        return

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"{path} has sha256 {actual_sha256}, expected {expected_sha256}",
        )
