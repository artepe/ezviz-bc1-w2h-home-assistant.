"""One source of truth for the app manifest version and published image tag."""

from pathlib import Path
import argparse
import re


def metadata(root: Path, addon: str = "ezviz_bc1_w2h") -> dict[str, str]:
    if addon not in ("ezviz_bc1_w2h", "ezviz_bc1_w2h_dev"):
        raise ValueError("Unknown app release directory")
    config = (root / addon / "config.yaml").read_text(encoding="utf-8")
    fields = {}
    for field in ("version", "image"):
        match = re.search(rf'^{field}:\s*"([^"\n]+)"\s*$', config, re.MULTILINE)
        if not match:
            raise ValueError(f"Missing quoted {field} in the app manifest")
        fields[field] = match.group(1)
    if not re.fullmatch(r"\d+\.\d+\.\d+", fields["version"]):
        raise ValueError("Use a numeric app release version")
    if not re.fullmatch(r"ghcr\.io/[a-z0-9._/-]+", fields["image"]):
        raise ValueError("Invalid GHCR image name")
    return fields


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--addon", default="ezviz_bc1_w2h", choices=("ezviz_bc1_w2h", "ezviz_bc1_w2h_dev"))
    args = parser.parse_args()
    for key, value in metadata(Path(__file__).resolve().parents[1], args.addon).items():
        print(f"{key}={value}")
