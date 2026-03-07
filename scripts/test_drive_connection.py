#!/usr/bin/env python3
"""
Test Google Drive connection (and optionally list files) using .env credentials.
Run from project root: python scripts/test_drive_connection.py [--folder-id FOLDER_ID]
Exits 0 on success.
"""
import os
import sys
from pathlib import Path

# Load .env from project root (verbiage)
root = Path(__file__).resolve().parent.parent
dotenv = root / ".env"
if dotenv.exists():
    for line in dotenv.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            v = v.strip().strip("'\"")
            os.environ.setdefault(k.strip(), v)

sys.path.insert(0, str(root))

def main() -> int:
    import argparse
    from app.drive_client import test_connection, list_docs_metadata, DriveClientError

    parser = argparse.ArgumentParser(description="Test Google Drive connection and optionally list Google Docs")
    parser.add_argument("--folder-id", default=None, help="If set, list Google Docs in this folder")
    args = parser.parse_args()

    try:
        test_connection()
    except DriveClientError as e:
        print("MYDEBUG → Drive connection failed:", e, file=sys.stderr)
        return 1
    print("MYDEBUG → Drive connection OK.")

    if args.folder_id:
        try:
            files = list_docs_metadata(folder_id=args.folder_id)
            if not files:
                print("MYDEBUG → No Google Docs in this folder.")
            else:
                for f in files:
                    modified = (f.get("modifiedTime") or "")[:10]
                    print("MYDEBUG →", f.get("id", ""), f.get("name", ""), modified)
        except DriveClientError as e:
            print("MYDEBUG → List failed:", e, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
