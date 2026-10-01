import base64
import binascii
import hashlib
import json
import os
import requests
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from odoo.exceptions import AccessDenied, ValidationError
from odoo.tools import consteq

from odoo.addons.base.models.res_users import KEY_CRYPT_CONTEXT

# 16 Hex chars (8 bytes) of the secret kept in plaintext as a lookup index
OAUTH_SECRET_INDEX_SIZE = 16
CIMD_MAX_DOCUMENT_BYTES = 5 * 1024


def _generate_secret(n_bytes=32):
    return binascii.hexlify(os.urandom(n_bytes)).decode()


def _generate_hash(input):
    return KEY_CRYPT_CONTEXT.hash(input)


def _verify_hash(input, hash):
    return KEY_CRYPT_CONTEXT.verify(input, hash)


def verifier_matches_challenge(code_verifier, code_challenge):
    if not code_verifier or not code_challenge:
        return False
    return consteq(challenge_from_verifier(code_verifier), code_challenge)


def challenge_from_verifier(code_verifier):
    """Compute the S256 PKCE code_challenge for a given code_verifier."""
    # RFC 7636 §4.2: challenge = BASE64URL-ENCODE(SHA256(ASCII(verifier))), and the padding '=' from the base64 must be stripped.
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


def oauth_base_url(env) -> str:
    return env['ir.config_parameter'].sudo().get_str('web.base.url')


def protected_resource_metadata_url(env) -> str:
    return f'{oauth_base_url(env)}/.well-known/oauth-protected-resource/mcp'


def check_mcp_oauth_user_access(user) -> None:
    if not user.active or not user._is_internal():
        raise AccessDenied(user.env._("Only internal users are allowed to use oauth for mcp"))


def is_redirect_uri_registered(redirect_uri: str, registered_uris: list[str]) -> bool:
    """Whether `redirect_uri` matches one of `registered_uris`.

    RFC 8252 §7.3: A native app (e.g. desktop, mobile or cli tool) can't host an HTTPS redirect
    endpoint and uses HTTP loopback redirect URIs instead. Also, a native app will bind to a new
    port on every run. So, the registered redirect URI won't include a port.
    """
    if not redirect_uri:
        return False

    redirect_uri_parts = urlsplit(redirect_uri)
    # RFC 6749 3.1.2: a redirect_uri must not include a fragment component.
    if redirect_uri_parts.fragment:
        return False

    if redirect_uri in registered_uris:
        return True

    # For http URLs, port-agnostic URL matching is performed. This implies that another malicious native app on
    # the device may be able to hijack the auth code However, only the original app is able to redeem the auth code
    # for an access token becaues only the original app has the PKCE verifier.
    for candidate_match in registered_uris:
        candidate_match_parts = urlsplit(candidate_match)

        if (
            candidate_match_parts.scheme == 'http'
            and redirect_uri_parts.scheme == candidate_match_parts.scheme
            and redirect_uri_parts.hostname == candidate_match_parts.hostname == '127.0.0.1'
            and redirect_uri_parts.path == candidate_match_parts.path
            and redirect_uri_parts.query == candidate_match_parts.query
        ):
            return True

    return False


def fetch_client_metadata_document(env, client_id: str) -> dict:
    url_parts = urlsplit(client_id)
    if url_parts.scheme != 'https' or not url_parts.hostname:
        raise ValidationError(env._("Invalid CIMD URL %s", client_id))

    cimd_allowed_urls = [
        url.strip() for url in env['ir.config_parameter'].sudo().get_str('cimd_allowed_urls').splitlines()
        if url.strip()
    ]
    if client_id not in cimd_allowed_urls:
        raise ValidationError(env._(
            "CIMD URL %(url)s isn't allowed. If you want this client to be able to connect, allow its URL in the settings.",
            url=client_id
        ))

    try:
        response = requests.get(client_id, timeout=5, allow_redirects=False, headers={'Accept': 'application/json'}, stream=True)
        content = response.raw.read(CIMD_MAX_DOCUMENT_BYTES + 1, decode_content=True)
        if response.status_code != 200 or len(content) > CIMD_MAX_DOCUMENT_BYTES:
            raise ValidationError(env._("Invalid CIMD URL %s.", client_id))
        cimd_document = json.loads(content)
    except (requests.RequestException, json.JSONDecodeError):
        raise ValidationError(env._("Invalid CIMD URL %s.", client_id))

    if cimd_document.get('client_id') != client_id:
        raise ValidationError(env._(
            "The client_id of the metadata document does not match the URL %(url)s it was fetched from.",
            url=client_id
        ))

    # Some clients like ChatGPT use private_key_jwt but also support none as token_endpoint_auth_method
    supported_auth_methods = cimd_document.get('token_endpoint_auth_methods_supported') or []
    if cimd_document.get('token_endpoint_auth_method') != 'none' and 'none' not in supported_auth_methods:
        raise ValidationError(env._("Unsupported token_endpoint_auth_method, The only supported option is 'none'"))
    cimd_document['token_endpoint_auth_method'] = 'none'

    cimd_document['redirect_uris'] = [normalize_localhost_to_ip(uri) for uri in cimd_document.get('redirect_uris') or []]
    validate_redirect_uris(env, cimd_document['redirect_uris'])

    cimd_document['client_name'] = cimd_document.get('client_name') or client_id
    return cimd_document


def normalize_localhost_to_ip(redirect_uri: str | None) -> str | None:
    """
    "localhost" resolution can be hijacked (DNS rebinding, hosts file) as per RFC 8252 §8.3.
    So it is substituted with 127.0.0.1 before any matching
    """
    if not redirect_uri:
        return redirect_uri

    parts = urlsplit(redirect_uri)
    if parts.hostname != 'localhost':
        return redirect_uri

    netloc = parts.netloc.lower().replace('localhost', '127.0.0.1', 1)
    return urlunsplit(parts._replace(netloc=netloc))


def validate_redirect_uris(env, redirect_uris: list) -> None:
    if not redirect_uris:
        raise ValidationError(env._("At least one redirect_uri is required."))

    for uri in redirect_uris:
        uri_parts = urlsplit(uri)
        # RFC 6749 3.1.2: the redirection endpoint URI MUST NOT include a fragment component.
        if uri_parts.fragment:
            raise ValidationError(env._(
                "Invalid redirect_uri %(uri)s: a redirect_uri must not include a fragment.",
                uri=uri
            ))

        is_uri_valid = (
            (uri_parts.scheme == 'https' and uri_parts.hostname)
            or (uri_parts.scheme == 'http' and uri_parts.hostname == '127.0.0.1')
        )

        if not is_uri_valid:
            raise ValidationError(env._(
                "Invalid redirect_uri %(uri)s: only https:// URIs are allowed (or http:// for a loopback address).",
                uri=uri
            ))


def merge_params_in_redirect_url(redirect_url: str, params: dict):
    """Merge 'params' into the query string of the redirect_url.

    request.redirect_query can't be used here: it unconditionally appends '?', which adds a
    second '?' when the redirect_uri already has a query string.
    """
    uri_parts = urlsplit(redirect_url)
    query = urlencode([*parse_qsl(uri_parts.query, keep_blank_values=True), *params.items()])
    return urlunsplit(uri_parts._replace(query=query))
