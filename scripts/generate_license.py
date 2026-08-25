"""Issue a signed GrowMaster Pro/Admin license without exposing the private key.

Example:
  python scripts/generate_license.py \
    --private-key ~/GrowMaster-License-Private-Key.pem \
    --edition pro --customer "Example Farm" \
    --device-id GM-XXXXXXXX-XXXXXXXXXXXX \
    --output license.txt
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a signed GrowMaster license")
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--edition", choices=("pro", "admin"), default="pro")
    parser.add_argument("--customer", required=True)
    parser.add_argument("--device-id", help="Installation UUID or GM activation request code")
    parser.add_argument("--expires", help="ISO date/time, e.g. 2027-12-31T23:59:59+00:00")
    parser.add_argument("--license-id", default=None)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    private_key = serialization.load_pem_private_key(
        args.private_key.read_bytes(), password=None
    )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit("Private key is not Ed25519.")

    payload = {
        "schema_version": 1,
        "license_id": args.license_id or f"GM-{secrets.token_hex(8).upper()}",
        "edition": args.edition,
        "customer": args.customer.strip(),
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "device_id": args.device_id or None,
        "expires_at": args.expires or None,
    }
    payload_bytes = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    token = f"{b64url(payload_bytes)}.{b64url(private_key.sign(payload_bytes))}"

    if args.output:
        args.output.write_text(token + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(token)


if __name__ == "__main__":
    main()
