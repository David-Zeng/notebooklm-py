"""Chrome extension support for the login command.

Provides helpers for loading Chrome extensions into Playwright during login,
enabling corporate Google Workspace accounts that require browser extensions
(e.g. Endpoint Verification) to authenticate successfully.
"""

import io
import os
import re
import sys
import zipfile
from pathlib import Path

import click

from ..paths import get_extensions_dir

# Chrome extension ID pattern: exactly 32 chars from a-p (base-16 of SHA256)
_EXTENSION_ID_RE = re.compile(r"^[a-p]{32}$")

# Chrome Web Store CRX download URL
_CRX_URL = (
    "https://clients2.google.com/service/update2/crx"
    "?response=redirect&prodversion=120.0.0.0"
    "&acceptformat=crx2,crx3"
    "&x=id%3D{extension_id}%26uc"
)


def resolve_extension_dir(extension_spec: str) -> Path:
    """Resolve an extension spec to an unpacked extension directory.

    Args:
        extension_spec: Either a Chrome Web Store extension ID (32 chars, a-p)
            or a filesystem path to an already-unpacked extension directory
            containing manifest.json.

    Returns:
        Path to the unpacked extension directory.

    Raises:
        click.ClickException: If the spec is invalid, the path has no manifest.json,
            or the CRX download fails.
    """
    # Case 1: looks like a Chrome extension ID
    if _EXTENSION_ID_RE.match(extension_spec):
        dest_dir = get_extensions_dir() / extension_spec
        manifest = dest_dir / "manifest.json"
        if manifest.exists():
            click.echo(f"Using cached extension at {dest_dir}", err=True)
        else:
            _download_and_unpack_crx(extension_spec, dest_dir)
        return dest_dir

    # Case 2: filesystem path
    path = Path(extension_spec).expanduser().resolve()
    if path.is_dir():
        if not (path / "manifest.json").exists():
            raise click.ClickException(
                f"Extension directory must contain manifest.json. Got: {path}"
            )
        return path

    # Neither a valid ID nor an existing directory
    raise click.ClickException(
        f"'{extension_spec}' is not a valid Chrome extension ID (32 chars, a-p) "
        f"or an existing directory path."
    )


def _strip_crx_header(data: bytes) -> bytes:
    """Strip the CRX2/CRX3 binary header to yield a raw ZIP payload.

    CRX3 format:
        4 bytes: magic "Cr24"
        4 bytes: version (little-endian uint32 = 3)
        4 bytes: header size (little-endian uint32)
        <header_size> bytes: protobuf header
        <ZIP data>

    CRX2 format:
        4 bytes: magic "Cr24"
        4 bytes: version (little-endian uint32 = 2)
        4 bytes: public key length
        4 bytes: signature length
        <pubkey_len + sig_len> bytes: key + signature
        <ZIP data>

    Args:
        data: Raw bytes from the CRX download.

    Returns:
        ZIP bytes ready for zipfile.ZipFile.

    Raises:
        click.ClickException: If no ZIP magic bytes can be found.
    """
    if not data.startswith(b"Cr24"):
        # Not a CRX — assume it's already a raw ZIP
        return data

    version = int.from_bytes(data[4:8], "little")
    if version == 3:
        header_size = int.from_bytes(data[8:12], "little")
        return data[12 + header_size :]
    elif version == 2:
        pubkey_len = int.from_bytes(data[8:12], "little")
        sig_len = int.from_bytes(data[12:16], "little")
        return data[16 + pubkey_len + sig_len :]

    # Unknown CRX version — scan for ZIP magic as a fallback
    zip_start = data.find(b"PK\x03\x04")
    if zip_start == -1:
        raise click.ClickException(
            "Downloaded file is not a valid CRX or ZIP archive. "
            "Try providing an unpacked extension directory with --extension /path/to/dir"
        )
    return data[zip_start:]


def _download_and_unpack_crx(extension_id: str, dest_dir: Path) -> None:
    """Download a Chrome extension CRX from the Web Store and unpack it.

    Args:
        extension_id: The Chrome Web Store extension ID.
        dest_dir: Directory to unpack the extension into.

    Raises:
        click.ClickException: On download failure or if manifest.json is missing
            after unpacking.
    """
    import httpx  # already a core dependency

    url = _CRX_URL.format(extension_id=extension_id)
    click.echo(f"Downloading extension {extension_id} ...", err=True)

    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise click.ClickException(
            f"Failed to download extension: HTTP {exc.response.status_code}.\n"
            "Try providing an already-unpacked extension with --extension /path/to/dir"
        ) from exc
    except Exception as exc:
        raise click.ClickException(
            f"Failed to download extension: {exc}.\n"
            "Try providing an already-unpacked extension with --extension /path/to/dir"
        ) from exc

    zip_data = _strip_crx_header(response.content)

    dest_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            zf.extractall(dest_dir)
    except zipfile.BadZipFile as exc:
        # Clean up partial extraction
        import shutil

        shutil.rmtree(dest_dir, ignore_errors=True)
        raise click.ClickException(
            f"Downloaded file is not a valid ZIP archive: {exc}.\n"
            "Try providing an already-unpacked extension with --extension /path/to/dir"
        ) from exc

    if not (dest_dir / "manifest.json").exists():
        import shutil

        shutil.rmtree(dest_dir, ignore_errors=True)
        raise click.ClickException(
            "Unpacked extension does not contain manifest.json. "
            "The download may be corrupted. Please retry or provide an unpacked extension directory."
        )

    click.echo(f"Extension unpacked to {dest_dir}", err=True)


def get_chrome_profile_path() -> Path | None:
    """Return the default Chrome user profile path for the current OS.

    Returns:
        Path to the Chrome 'Default' profile directory, or None if the
        platform is not recognised.

    Note:
        The *parent* of this path (the 'User Data' directory) is what
        Playwright's launch_persistent_context expects as user_data_dir.
    """
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Google" / "Chrome" / "Default"
    if sys.platform == "linux":
        return home / ".config" / "google-chrome" / "Default"
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            return Path(local_app_data) / "Google" / "Chrome" / "User Data" / "Default"
    return None
