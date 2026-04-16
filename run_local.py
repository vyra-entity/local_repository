#!/usr/bin/env python3
"""Start the VYRA Local Repository without Docker.

Usage:
    python run_local.py [--host HOST] [--port PORT] [--data-dir PATH] [--reload]

The service exposes the same REST API as vyra_storage_pool:
  GET /health
  GET /index.json             ← consumed by v2_modulemanager file-based client
  GET /api/v1/{type}
  GET /api/v1/{type}/{name}/{version}
  GET /files/{type}/{name}/{version}/{file}

Set base_url in repository_config.json to:
  http://localhost:8100        (HTTP local service)

Or use type=file-based with url pointing directly to the data/ folder:
  file:///path/to/local_repository/data
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Allow running from any working directory
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import uvicorn
except ImportError:
    print("❌  uvicorn is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)


def main() -> None:
    """Parse CLI arguments and start uvicorn."""
    parser = argparse.ArgumentParser(description="Start the VYRA Local Repository service.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8100, help="Bind port (default: 8100)")
    parser.add_argument(
        "--data-dir",
        default=str(REPO_ROOT / "data"),
        help="Path to the data directory (default: ./data)",
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload (development mode)"
    )
    parser.add_argument(
        "--log-level", default="info", choices=["debug", "info", "warning", "error"]
    )
    args = parser.parse_args()

    # Inject settings via environment so pydantic_settings picks them up
    os.environ.setdefault("VYRA_LOCAL_REPO_HOST", args.host)
    os.environ.setdefault("VYRA_LOCAL_REPO_PORT", str(args.port))
    os.environ["VYRA_LOCAL_REPO_DATA_DIR"] = args.data_dir
    os.environ.setdefault("VYRA_LOCAL_REPO_LOG_LEVEL", args.log_level.upper())

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    print(f"🚀  VYRA Local Repository")
    print(f"   Data dir : {args.data_dir}")
    print(f"   Endpoint : http://{args.host}:{args.port}")
    print(f"   Docs     : http://{args.host}:{args.port}/docs")
    print()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        app_dir=str(REPO_ROOT),
    )


if __name__ == "__main__":
    main()
