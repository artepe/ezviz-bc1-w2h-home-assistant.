"""Offline, no-clobber import of an owner's SDK credential export.

Never discovers keys, guesses channels, contacts EZVIZ or prints source data.
Run in the DEV container so /data belongs to the intended add-on.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import stat
import tempfile

from local_capture import read_credentials
from local_diagnostics import LocalCredentialError


def install(source: Path, directory: Path, serial: str, channel: int, slot: int):
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError
    return install_data(json.loads(raw), directory, serial, channel, slot)


def install_data(data, directory: Path, serial: str, channel: int, slot: int, replace=False):
    if type(replace) is not bool:
        raise ValueError
    if type(slot) is not int or not 1 <= slot <= 16:
        raise ValueError
    if type(channel) is not int or not 1 <= channel <= 256:
        raise LocalCredentialError("CHANNEL_INVALID")
    if len(json.dumps(data).encode("utf-8")) > 65536:
        raise ValueError
    if not isinstance(data, dict) or data.get("serial") != serial:
        raise ValueError
    # An explicit mapping is required; never infer from slot, suffix or order.
    if "channel" in data and (type(data["channel"]) is not int or data["channel"] != channel):
        raise ValueError
    selected = {key: data[key] for key in
                ("serial", "endpoint", "cas", "media_key", "media_key_hex") if key in data}
    selected["channel"] = channel
    # Discard unrelated fields, including tokens accidentally included in exports.
    selected["endpoint"] = {key: data["endpoint"][key] for key in
                            ("host", "command_port", "stream_port") if key in data["endpoint"]}
    selected["cas"] = {key: data["cas"][key] for key in
                       ("key", "operation_code", "encrypt_type") if key in data["cas"]}
    # Validate AES representation according to the pinned SDK, without importing it.
    key = selected["cas"]["key"]
    if not isinstance(key, str):
        raise ValueError
    if len(key.encode("utf-8")) != 16:
        try:
            decoded = base64.b64decode(key, validate=True)
        except binascii.Error:
            raise ValueError from None
        if len(decoded) != 16:
            raise ValueError
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".local-import-", delete=False) as output:
            temporary = Path(output.name)
            os.fchmod(output.fileno(), 0o600)
            output.write(json.dumps(selected).encode("utf-8"))
            output.flush()
            os.fsync(output.fileno())
        read_credentials(temporary, serial)
        # Atomic publication fails if a file or symlink already occupies the slot.
        target = directory / f"local_camera_{slot}.json"
        if replace:
            if target.is_symlink():
                raise ValueError
            os.replace(temporary, target)
        else:
            os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--directory", type=Path, default=Path("/data"))
    parser.add_argument("--serial", required=True)
    parser.add_argument("--channel", type=int, required=True)
    parser.add_argument("--slot", type=int, choices=range(1, 17), required=True)
    args = parser.parse_args(argv)
    try:
        install(args.source, args.directory, args.serial, args.channel, args.slot)
    except FileExistsError:
        print("LOCAL_IMPORT:DESTINATION_EXISTS")
        return 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        print("LOCAL_IMPORT:INVALID_INPUT")
        return 1
    print("LOCAL_IMPORT:FORMAT_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
