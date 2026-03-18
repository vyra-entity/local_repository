#!/usr/bin/env python3
"""
pack_base_image.py
Exports Docker base images (e.g. vyra_base_image) as full archives into the
local_repository/images/ store and updates images/index.json.

Usage:
  # Pack all built variants of vyra_base_image
  python3 tools/pack_base_image.py vyra_base_image

  # Pack a specific tag
  python3 tools/pack_base_image.py vyra_base_image:production

  # Pack multiple base images
  python3 tools/pack_base_image.py vyra_base_image vyra_base_image_slim

  # Pack a completely different infrastructure image
  python3 tools/pack_base_image.py redis:7 --name redis --version 7.0.0

Output structure:
  images/{name}/{version}/{name}_{variant}_{version}.tar.gz
  images/{name}/{version}/metadata.json
  images/index.json
"""

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
IMAGES_DIR = REPO_DIR / "images"

# Known base image variants: (image_name, variant_suffix)
BASE_IMAGE_VARIANTS = {
    "vyra_base_image": ["development", "production"],
    "vyra_base_image_slim": ["development", "production"],
}


def sha256_file(path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess command."""
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
    )


def image_exists(tag: str) -> bool:
    """Check whether a Docker image tag is locally available."""
    result = subprocess.run(
        ["docker", "image", "inspect", tag],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def get_image_label(tag: str, label_key: str) -> str | None:
    """Read a label value from a local Docker image."""
    fmt = f"{{{{index .Config.Labels \"{label_key}\"}}}}"
    try:
        result = _run(["docker", "inspect", "--format", fmt, tag])
        value = result.stdout.strip()
        return value if value else None
    except subprocess.CalledProcessError:
        return None


def get_image_version(tag: str) -> str | None:
    """Return the semantic version encoded in the image label, or None."""
    return get_image_label(tag, "org.opencontainers.image.version")


def export_full_image(image_tag: str, output_path: Path) -> None:
    """Export a Docker image as a gzip-compressed tar archive.

    Args:
        image_tag: Full image tag to export (e.g. 'vyra_base_image:production').
        output_path: Destination .tar.gz path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tar.gz.tmp")

    print(f"   💾 Exporting {image_tag} → {output_path.name} ...")
    try:
        # docker save | gzip
        save_proc = subprocess.Popen(
            ["docker", "save", image_tag],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        with open(tmp_path, "wb") as out_f:
            with gzip.GzipFile(fileobj=out_f, mode="wb") as gz_f:
                for chunk in iter(lambda: save_proc.stdout.read(65536), b""):
                    gz_f.write(chunk)
        save_proc.wait()
        if save_proc.returncode != 0:
            err = save_proc.stderr.read().decode()
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError(f"docker save failed: {err}")
        tmp_path.rename(output_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def pack_image_tag(
    image_tag: str,
    logical_name: str,
    variant: str,
    version: str | None = None,
) -> dict | None:
    """Pack a single image tag into the images store.

    Args:
        image_tag: Docker image tag (e.g. 'vyra_base_image:production').
        logical_name: Logical name used as directory name (e.g. 'vyra_base_image').
        variant: Variant string used in filename (e.g. 'production', 'development').
        version: Explicit version override. If None reads from image label.

    Returns:
        Image entry dict suitable for index.json, or None if skipped/failed.
    """
    if not image_exists(image_tag):
        print(f"   ⚠️  Image not found locally: {image_tag} — skipping")
        return None

    if version is None:
        version = get_image_version(image_tag)
    if not version:
        print(f"   ⚠️  No version label on {image_tag}. Use --version or add LABEL org.opencontainers.image.version")
        return None

    version_dir = IMAGES_DIR / logical_name / version
    version_dir.mkdir(parents=True, exist_ok=True)

    archive_name = f"{logical_name}_{variant}_{version}.tar.gz"
    archive_path = version_dir / archive_name
    relative_path = f"images/{logical_name}/{version}/{archive_name}"

    export_full_image(image_tag, archive_path)

    checksum = sha256_file(archive_path)
    size = archive_path.stat().st_size
    synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = {
        "name": logical_name,
        "variant": variant,
        "version": version,
        "image_tag": image_tag,
        "filename": relative_path,
        "synced_at": synced_at,
        "size": size,
        "checksum": checksum,
    }

    # Write per-version metadata.json
    metadata_path = version_dir / "metadata.json"
    existing_meta: dict = {}
    if metadata_path.exists():
        with open(metadata_path) as f:
            existing_meta = json.load(f)

    existing_variants: list = existing_meta.get("variants", [])
    # Replace or add variant entry
    existing_variants = [v for v in existing_variants if v.get("variant") != variant]
    existing_variants.append(entry)

    metadata = {
        "name": logical_name,
        "version": version,
        "variants": sorted(existing_variants, key=lambda x: x["variant"]),
        "last_updated": synced_at,
    }
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"   ✅ Packed: {archive_name} ({size // 1024 // 1024} MB)")
    return entry


def update_images_index(packed_entries: list[dict]) -> None:
    """Update images/index.json with newly packed image entries."""
    index_path = IMAGES_DIR / "index.json"
    index: dict = {}
    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)

    existing_images: list = index.get("images", [])

    # Merge: replace matching (name, variant, version) tuples
    for entry in packed_entries:
        key = (entry["name"], entry["variant"], entry["version"])
        existing_images = [
            e for e in existing_images
            if (e["name"], e["variant"], e["version"]) != key
        ]
        existing_images.append(entry)

    # Keep images/index.json stateless: only the images list, no repository metadata
    # Repository-level info (name, description, etc.) lives in local_repository/index.json
    index["images"] = sorted(
        existing_images,
        key=lambda x: (x["name"], x["variant"], x["version"]),
    )

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n📝 images/index.json updated ({len(index['images'])} entries)")


def parse_image_spec(spec: str) -> tuple[str, str, str]:
    """Parse an image spec string into (image_tag, logical_name, variant).

    Handles:
      - 'vyra_base_image'            → probes all known variants
      - 'vyra_base_image:production' → single variant
      - 'redis:7'                    → arbitrary image, name=redis, variant=7
    """
    if ":" in spec:
        name_part, tag_part = spec.rsplit(":", 1)
    else:
        name_part = spec
        tag_part = None
    return name_part, tag_part  # (logical_name_candidate, variant_or_None)


def main() -> None:  # noqa: C901
    """Main entry point for pack_base_image."""
    parser = argparse.ArgumentParser(
        description="Export Docker base images into local_repository/images/"
    )
    parser.add_argument(
        "images",
        nargs="+",
        metavar="IMAGE",
        help=(
            "Image(s) to pack. Examples: 'vyra_base_image', "
            "'vyra_base_image:production', 'redis:7'"
        ),
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Override logical name used as directory / index key (optional)",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Override version (default: read from org.opencontainers.image.version label)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("📦 Packing base images into local_repository/images/")
    print("=" * 60)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    all_packed: list[dict] = []

    for spec in args.images:
        logical_name_candidate, variant_or_none = parse_image_spec(spec)
        logical_name = args.name if args.name else logical_name_candidate

        print(f"\n🔍 Processing: {spec}")

        if variant_or_none is not None:
            # Single tag specified explicitly
            image_tag = spec
            variant = variant_or_none
            entry = pack_image_tag(image_tag, logical_name, variant, version=args.version)
            if entry:
                all_packed.append(entry)
        else:
            # No tag → probe known variants
            known_variants = BASE_IMAGE_VARIANTS.get(logical_name_candidate)
            if known_variants is None:
                # Unknown image: cannot enumerate variants; require explicit tag
                print(
                    f"   ❌ Unknown image '{logical_name_candidate}'. "
                    "Specify a full tag like '{logical_name}:variant' or add it to BASE_IMAGE_VARIANTS."
                )
                sys.exit(1)

            found_any = False
            for variant in known_variants:
                image_tag = f"{logical_name_candidate}:{variant}"
                entry = pack_image_tag(image_tag, logical_name, variant, version=args.version)
                if entry:
                    all_packed.append(entry)
                    found_any = True

            if not found_any:
                print(f"   ❌ No locally built variants found for '{logical_name_candidate}'")
                print(
                    "   ℹ️  Build base images first:\n"
                    "       cd /VOS2_WORKSPACE && ./tools/vyra_up.sh"
                )
                sys.exit(1)

    if all_packed:
        update_images_index(all_packed)

    print()
    print(f"📍 Repository path: {REPO_DIR}")
    print("=" * 60)
    print("✅ Done")
    print("=" * 60)


if __name__ == "__main__":
    main()
