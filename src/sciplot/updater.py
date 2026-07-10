from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .version import APP_VERSION


GITHUB_RELEASES_URL = "https://github.com/Kevin-kaiquan/SciPlot/releases"
GITHUB_LATEST_RELEASE_URL = f"{GITHUB_RELEASES_URL}/latest"
GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/Kevin-kaiquan/SciPlot/releases/latest"
APPROVED_GITHUB_HOSTS = {"api.github.com", "github.com", "www.github.com"}


class UpdateCheckError(RuntimeError):
    pass


class UpdateDownloadError(RuntimeError):
    pass


def _validate_github_https_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()
    github_content_host = hostname.endswith(".githubusercontent.com")
    if parsed.scheme != "https" or (hostname not in APPROVED_GITHUB_HOSTS and not github_content_host):
        raise ValueError("The update URL is not an approved GitHub HTTPS URL.")


class _GitHubHTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request: Any, file_pointer: Any, code: int, message: str, headers: Any, new_url: str) -> Any:
        _validate_github_https_url(new_url)
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def _open_github_url(request: urllib.request.Request, timeout: int, use_system_proxy: bool = True) -> Any:
    _validate_github_https_url(request.full_url)
    proxy_handler = urllib.request.ProxyHandler() if use_system_proxy else urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler, _GitHubHTTPSRedirectHandler())
    response = opener.open(request, timeout=timeout)
    try:
        _validate_github_https_url(response.geturl())
    except Exception:
        response.close()
        raise
    return response


def _network_routes(short_timeout: int, long_timeout: int) -> list[tuple[bool, int]]:
    routes = [(False, short_timeout)]
    if urllib.request.getproxies():
        routes.append((True, long_timeout))
    else:
        routes.append((False, long_timeout))
    return routes


@dataclass
class UpdateInfo:
    version: str
    release_url: str
    asset_name: str = ""
    asset_url: str = ""
    asset_size: int = 0
    asset_sha256: str = ""


def _version_key(value: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in re.findall(r"\d+", value)]
    padded = (parts + [0, 0, 0, 0])[:4]
    return padded[0], padded[1], padded[2], padded[3]


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    return _version_key(latest) > _version_key(current)


def preferred_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    names = [(asset, str(asset.get("name") or "").lower()) for asset in assets]
    if sys.platform.startswith("win"):
        return next((asset for asset, name in names if name.endswith(".msi") and "windows" in name), None) or next(
            (asset for asset, name in names if name.endswith(".msi")), None
        )
    if sys.platform == "darwin":
        architecture = "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "intel"
        return next((asset for asset, name in names if name.endswith(".dmg") and architecture in name), None) or next(
            (asset for asset, name in names if name.endswith(".dmg")), None
        )
    return None


def _expected_asset_name() -> str:
    if sys.platform.startswith("win"):
        return "SciPlot-Windows-x64.msi"
    if sys.platform == "darwin":
        architecture = "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "intel"
        return f"SciPlot-macOS-{architecture}.dmg"
    return ""


def _release_asset_url(version: str, asset_name: str) -> str:
    if not asset_name:
        return ""
    tag = urllib.parse.quote(f"v{version}", safe="")
    name = urllib.parse.quote(asset_name, safe="")
    return f"{GITHUB_RELEASES_URL}/download/{tag}/{name}"


def _normalized_digest(value: Any) -> str:
    digest = str(value or "").strip().lower()
    return digest.removeprefix("sha256:") if re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", digest) else ""


def _update_info_from_payload(payload: dict[str, Any], current_version: str) -> UpdateInfo | None:
    latest = str(payload.get("tag_name") or payload.get("name") or "").lstrip("v")
    if not latest or not is_newer_version(latest, current_version):
        return None
    assets = payload.get("assets") if isinstance(payload.get("assets"), list) else []
    asset = preferred_asset([item for item in assets if isinstance(item, dict)])
    asset_name = str(asset.get("name") or "") if asset else _expected_asset_name()
    asset_url = str(asset.get("browser_download_url") or "") if asset else _release_asset_url(latest, asset_name)
    return UpdateInfo(
        version=latest,
        release_url=str(payload.get("html_url") or f"{GITHUB_RELEASES_URL}/tag/v{latest}"),
        asset_name=asset_name,
        asset_url=asset_url,
        asset_size=int(asset.get("size") or 0) if asset else 0,
        asset_sha256=_normalized_digest(asset.get("digest")) if asset else "",
    )


def _fetch_api_payload() -> dict[str, Any]:
    last_error: Exception | None = None
    for use_system_proxy, timeout in _network_routes(12, 30):
        request = urllib.request.Request(
            GITHUB_LATEST_RELEASE_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": f"SciPlot/{APP_VERSION}"},
        )
        try:
            with _open_github_url(request, timeout=timeout, use_system_proxy=use_system_proxy) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("GitHub returned an invalid release document.")
            return payload
        except Exception as exc:
            last_error = exc
    if last_error is None:
        raise OSError("No GitHub connection route was available.")
    raise last_error


def _fetch_release_redirect(current_version: str) -> UpdateInfo | None:
    last_error: Exception | None = None
    for use_system_proxy, timeout in _network_routes(12, 30):
        request = urllib.request.Request(
            GITHUB_LATEST_RELEASE_URL,
            headers={"User-Agent": f"SciPlot/{APP_VERSION}"},
            method="HEAD",
        )
        try:
            with _open_github_url(request, timeout=timeout, use_system_proxy=use_system_proxy) as response:
                release_url = response.geturl()
            match = re.search(r"/releases/tag/v?([^/?#]+)", release_url)
            if not match:
                raise ValueError("GitHub did not redirect to a release tag.")
            latest = urllib.parse.unquote(match.group(1)).lstrip("v")
            if not is_newer_version(latest, current_version):
                return None
            asset_name = _expected_asset_name()
            return UpdateInfo(
                version=latest,
                release_url=release_url,
                asset_name=asset_name,
                asset_url=_release_asset_url(latest, asset_name),
            )
        except Exception as exc:
            last_error = exc
    if last_error is None:
        raise OSError("No GitHub connection route was available.")
    raise last_error


def fetch_latest_release(current_version: str = APP_VERSION) -> UpdateInfo | None:
    try:
        return _update_info_from_payload(_fetch_api_payload(), current_version)
    except Exception:
        pass
    try:
        return _fetch_release_redirect(current_version)
    except Exception as exc:
        message = "SciPlot could not reach GitHub. Check the internet connection, proxy or VPN, and firewall, then try again."
        raise UpdateCheckError(message) from exc


def _response_total_size(response: Any, starting_size: int) -> int:
    content_range = str(response.headers.get("Content-Range") or "")
    match = re.search(r"/(\d+)$", content_range)
    if match:
        return int(match.group(1))
    content_length = int(response.headers.get("Content-Length") or 0)
    status = int(getattr(response, "status", response.getcode()) or 0)
    return starting_size + content_length if status == 206 else content_length


def _download_once(
    info: UpdateInfo,
    temporary: Path,
    progress: Callable[[int, str], None],
    use_system_proxy: bool,
    timeout: int,
) -> int:
    starting_size = temporary.stat().st_size if temporary.exists() else 0
    headers = {
        "Accept": "application/octet-stream",
        "Range": f"bytes={starting_size}-",
        "User-Agent": f"SciPlot/{APP_VERSION}",
    }
    request = urllib.request.Request(info.asset_url, headers=headers)
    with _open_github_url(request, timeout=timeout, use_system_proxy=use_system_proxy) as response:
        status = int(getattr(response, "status", response.getcode()) or 0)
        append = starting_size > 0 and status == 206
        if not append:
            starting_size = 0
        total = _response_total_size(response, starting_size)
        received = starting_size
        with temporary.open("ab" if append else "wb") as output:
            while True:
                chunk = response.read(1024 * 512)
                if not chunk:
                    break
                output.write(chunk)
                received += len(chunk)
                percentage = int(received * 100 / total) if total else 0
                progress(percentage, f"{received / 1024 / 1024:.1f} MB")
    return total


def _validate_download(path: Path, info: UpdateInfo, response_size: int = 0) -> None:
    actual_size = path.stat().st_size if path.exists() else 0
    expected_size = info.asset_size or response_size
    if actual_size <= 0 or (expected_size and actual_size != expected_size):
        raise ValueError("The downloaded installer size does not match the GitHub release metadata.")
    if info.asset_sha256:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != info.asset_sha256.lower():
            raise ValueError("The downloaded installer checksum does not match the GitHub release digest.")


def download_update(info: UpdateInfo, destination: Path, progress: Callable[[int, str], None]) -> Path:
    _validate_github_https_url(info.asset_url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    if destination.exists() and (info.asset_size or info.asset_sha256):
        try:
            _validate_download(destination, info)
            progress(100, f"{destination.stat().st_size / 1024 / 1024:.1f} MB")
            return destination
        except ValueError:
            destination.unlink(missing_ok=True)
    if temporary.exists() and (info.asset_size or info.asset_sha256):
        try:
            _validate_download(temporary, info)
            temporary.replace(destination)
            progress(100, f"{destination.stat().st_size / 1024 / 1024:.1f} MB")
            return destination
        except ValueError:
            if info.asset_size and temporary.stat().st_size >= info.asset_size:
                temporary.unlink(missing_ok=True)

    last_error: Exception | None = None
    for use_system_proxy, timeout in _network_routes(45, 150):
        try:
            response_size = _download_once(info, temporary, progress, use_system_proxy, timeout)
            _validate_download(temporary, info, response_size)
            temporary.replace(destination)
            progress(100, f"{destination.stat().st_size / 1024 / 1024:.1f} MB")
            return destination
        except Exception as exc:
            last_error = exc
            if isinstance(exc, ValueError):
                temporary.unlink(missing_ok=True)
    message = "SciPlot could not download the update package. Check the connection and free disk space, then try again."
    raise UpdateDownloadError(message) from last_error
