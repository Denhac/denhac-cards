import base64
import hmac
import json
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from datetime import datetime, timedelta, timezone


@dataclass
class DecodingResult:
    valid_signature: bool
    expired: bool = field(default=True)
    data: Dict[str, Any] = field(default_factory=lambda: {})

    @property
    def ok(self) -> bool:
        return self.valid_signature and not self.expired


class DataSigning:
    def __init__(self, secret_key):
        self.__secret_key = secret_key

    def encode(self, expires_in_seconds: int, data: Optional[Dict[str, Any]] = None) -> str:
        if data is None:
            data = {}
        data = data.copy()

        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=expires_in_seconds)

        data["expires"] = expires.isoformat()

        payload = json.dumps(data, sort_keys=True, separators=(',', ':'))
        payload_b64 = base64.urlsafe_b64encode(payload.encode('ascii'))

        signature = base64.urlsafe_b64encode(self.__get_signature(payload_b64))

        return f"{payload_b64.decode('ascii')}.{signature.decode('ascii')}"

    def decode(self, signed_payload: str) -> DecodingResult:
        split_signed_payload: list[str] = signed_payload.split('.')

        if len(split_signed_payload) != 2:
            return DecodingResult(
                valid_signature=False
            )

        payload_b64, signature_b64 = split_signed_payload

        actual_signature = self.__get_signature(payload_b64.encode('ascii'))
        signature_to_test = base64.urlsafe_b64decode(signature_b64)

        if actual_signature != signature_to_test:
            return DecodingResult(
                valid_signature=False
            )

        # From this point on, the signature should be valid

        data = json.loads(base64.urlsafe_b64decode(payload_b64))

        if not isinstance(data, dict):
            return DecodingResult(
                valid_signature=True,
                expired=True
            )

        if "expires" not in data:
            return DecodingResult(
                valid_signature=True,
                expired=True
            )

        now = datetime.now(timezone.utc)
        try:
            expires_time = datetime.fromisoformat(data["expires"])
        except ValueError:  # Invalid isoformat string
            return DecodingResult(
                valid_signature=True,
                expired=True
            )

        if expires_time < now:  # We're expired!
            return DecodingResult(
                valid_signature=True,
                expired=True
            )

        # From this point on, we should have a valid signature AND we know we're not expired.
        return DecodingResult(
            valid_signature=True,
            expired=False,
            data=data
        )

    def __get_signature(self, payload_b64):
        return hmac.new(
            self.__secret_key.encode('ascii'),
            base64.urlsafe_b64encode(payload_b64),
            'sha256'
        ).digest()
