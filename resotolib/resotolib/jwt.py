import os
import jwt
import base64
import hashlib
import time
from resotolib.args import ArgumentParser
from resotolib.x509 import cert_fingerprint
from typing import Any, Optional, Tuple, Dict, Mapping, Union, cast
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.x509.base import Certificate

from resotolib.types import Json


def key_from_psk(psk: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """Derive a 256 bit key from a passphrase/pre-shared-key.
    A salt can be optionally provided. If not one will be generated.
    Returns both the key and the salt.
    """
    if salt is None:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", psk.encode(), salt, 100000)
    return key, salt


def encode_jwt(
    payload: Dict[str, Any],
    key: Union[str, RSAPrivateKey],
    headers: Optional[Dict[str, str]] = None,
    expire_in: int = 300,
    public_key: Optional[RSAPublicKey] = None,
) -> str:
    """Encodes a payload into a JWT either using a pre-shared-key or an RSA private key."""
    payload = dict(payload)
    if headers is None:
        headers = {}
    headers.update({"typ": "JWT"})
    if expire_in > 0 and "exp" not in payload:
        payload.update({"exp": int(time.time()) + expire_in})

    if isinstance(key, RSAPrivateKey):
        return encode_jwt_pki(payload, key, headers, public_key)
    else:
        return encode_jwt_psk(payload, key, headers)


def encode_jwt_pki(
    payload: Dict[str, Any],
    private_key: RSAPrivateKey,
    headers: Dict[str, str],
    public_key: Optional[RSAPublicKey] = None,
) -> str:
    """Encodes a payload into a JWT either using an RSA private key."""
    headers.update({"alg": "RS256"})
    if public_key is not None:
        headers.update({"x5t#S256": cert_fingerprint(public_key, "SHA256")})
    return jwt.encode(payload, private_key, algorithm="RS256", headers=headers)  # type: ignore


def encode_jwt_psk(
    payload: Dict[str, Any],
    psk: str,
    headers: Dict[str, str],
) -> str:
    """Encodes a payload into a JWT and signs using a key derived from a pre-shared-key.
    Stores the key's salt in the JWT headers.
    """
    key, salt = key_from_psk(psk)
    salt_encoded = base64.standard_b64encode(salt).decode("utf-8")
    headers.update({"alg": "HS256", "salt": salt_encoded})
    return jwt.encode(payload, key, algorithm="HS256", headers=headers)  # type: ignore


def decode_jwt(
    encoded_jwt: str, psk_or_cert: Union[str, Certificate, RSAPublicKey], options: Optional[Dict[str, Any]] = None
) -> Json:
    """Decode a JWT using a key derived from a pre-shared-key and a salt stored
    in the JWT headers or an RSA public key.
    """
    alg = jwt.get_unverified_header(encoded_jwt).get("alg")
    if alg == "RS256":
        assert isinstance(psk_or_cert, (Certificate, RSAPublicKey))
        return decode_jwt_pki(encoded_jwt, psk_or_cert, options)
    elif alg == "HS256":
        assert isinstance(psk_or_cert, str)
        return decode_jwt_psk(encoded_jwt, psk_or_cert, options)
    else:
        raise ValueError(f"Unsupported JWT algorithm: {alg}")


def decode_jwt_psk(encoded_jwt: str, psk: str, options: Optional[Dict[str, Any]] = None) -> Json:
    """Decode a JWT using a key derived from a pre-shared-key and a salt stored
    in the JWT headers.
    """
    salt_encoded = jwt.get_unverified_header(encoded_jwt).get("salt")
    salt = base64.standard_b64decode(salt_encoded) if salt_encoded else None
    key, _ = key_from_psk(psk, salt)
    return jwt.decode(encoded_jwt, key, algorithms=["HS256"], options=options)  # type: ignore


def decode_jwt_pki(
    encoded_jwt: str, public_key: Union[Certificate, RSAPublicKey], options: Optional[Dict[str, Any]] = None
) -> Json:
    """Decode a JWT using an RSA public key."""
    if isinstance(public_key, Certificate):
        public_key = cast(RSAPublicKey, public_key.public_key())
        assert isinstance(public_key, RSAPublicKey)
    return jwt.decode(encoded_jwt, public_key, algorithms=["RS256"], options=options)  # type: ignore


def encode_jwt_to_headers(
    http_headers: Dict[str, str],
    payload: Dict[str, Any],
    key: Union[str, RSAPrivateKey],
    scheme: str = "Bearer",
    headers: Optional[Dict[str, str]] = None,
    expire_in: int = 300,
    public_key: Optional[RSAPublicKey] = None,
) -> Dict[str, str]:
    """Takes a payload and psk turns them into a JWT and adds that to a http headers
    dictionary. Also returns that dict.
    """
    http_headers.update({"Authorization": f"{scheme} {encode_jwt(payload, key, headers, expire_in, public_key)}"})
    return http_headers


def decode_jwt_from_headers(
    http_headers: Mapping[str, str],
    psk_or_cert: Union[str, Certificate, RSAPublicKey],
    scheme: str = "Bearer",
    options: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, str]]:
    """Retrieves the Authorization header from a http headers dictionary and
    passes it to `decode_jwt_from_header_value()` to return the decoded payload.
    """
    authorization_header = {str(k).capitalize(): v for k, v in http_headers.items()}.get("Authorization")
    if authorization_header is None:
        return None
    return decode_jwt_from_header_value(authorization_header, psk_or_cert, scheme, options)


def decode_jwt_from_header_value(
    authorization_header: str,
    psk_or_cert: Union[str, Certificate, RSAPublicKey],
    scheme: str = "Bearer",
    options: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, str]]:
    """Decodes a JWT payload from a http Authorization header value."""
    if (
        len(authorization_header) <= len(scheme) + 1
        or str(authorization_header[0 : len(scheme)]).lower() != scheme.lower()
        or authorization_header[len(scheme) : len(scheme) + 1] != " "
    ):
        return None
    encoded_jwt = authorization_header[len(scheme) + 1 :]
    return decode_jwt(encoded_jwt, psk_or_cert, options)


def add_args(arg_parser: ArgumentParser) -> None:
    arg_parser.add_argument(
        "--psk",
        help="Pre-shared key",
        type=lambda x: x if len(x) > 0 else None,
        default=None,
        dest="psk",
    )
