import re
import secrets

from markupsafe import escape

from odoo.tools import hmac

PROVISIONING_URI_SCHEME = "linphone-config:"
PROVISIONING_TOKEN_SCOPE = "voip_linphone_provisioning"
PROVISIONING_KEY_SCOPE = "voip_linphone_provisioning_key"
PROVISIONING_TOKEN_EXPIRATION_HOURS = 1

PROVISIONING_KIND_BOOTSTRAP = "bootstrap"
PROVISIONING_KIND_REFRESH = "refresh"

# Sent by the phone on every refresh fetch
PROVISIONING_KEY_HEADER = "X-Odoo-Provisioning-Key"

# Max provisioned linphones per user. A new provisioning will work
# but the oldest one won't be able to refresh anymore.
PROVISIONING_MAX_DEVICES = 10

NAT_POLICY_REF = "odoo_nat_policy"

# Whether an entry is restated every time the document is applied.
#
# liblinphone writes an entry only when the key is absent, unless the entry
# carries overwrite="true" (xml2lpc.c, processEntry). Since the phone
# re-downloads this document at every core start, that attribute is what
# separates the settings we own from the ones the user owns:
#
#   _PINNED  the value is a requirement of the platform. A phone that drifted
#            away from it is brought back at the next start.
#   _SEEDED  the value is only our starting point. It is written on a fresh
#            install and never touched again, so a user who changes it in the
#            app keeps their choice.
#
# A setting we have no opinion about is simply absent from the document.
_PINNED = True
_SEEDED = False

_PROVISIONING_SECTIONS = [
    ("sip", [
        ("default_proxy", "0", _PINNED),  # Forces to use proxy_0
        # The app's default rc asks for random UDP and TCP listening ports
        # this client has no use for: the account is pinned to transport=tls
        # and every inbound INVITE arrives on the registered TLS connection.
        # Inbound TLS is never listened on either, so sip_tls_port is left alone.
        ("sip_port", "0", _PINNED),  # Disables UDP socket
        ("sip_tcp_port", "0", _PINNED),  # Disables TCP socket
        ("media_encryption", "dtls", _PINNED),
        ("media_encryption_mandatory", "1", _PINNED),
        # The three below are rows of the Advanced calls settings page, which
        # the open settings screen reaches. Wazo expects DTMF as RFC 2833, and
        # early media would ring on the 183 the PBX sends to carry its own
        # progress announcements.
        ("use_rfc2833", "1", _PINNED),
        ("use_info", "0", _PINNED),
        ("incoming_calls_early_media", "0", _PINNED),
    ]),
    ("net", [
        ("nat_policy_ref", NAT_POLICY_REF, _PINNED),
        # Restated at its liblinphone default so that the Calls section cannot
        # leave a phone sending at a bitrate the network will not carry.
        ("adaptive_rate_control", "1", _PINNED),
        # A phone restricted to Wi-Fi silently stops registering on mobile
        # data, so the starting value is explicit - but this is one of the
        # switches the user is meant to own.
        ("wifi_only", "0", _SEEDED),
    ]),
    ("nat_policy_0", [
        # A fixed ref is what keeps the phone reusing this policy instead of
        # appending a new nat_policy_N section on every application.
        ("ref", NAT_POLICY_REF, _PINNED),
        ("protocols", "stun,ice", _PINNED),
        ("stun_server", "stun.l.google.com:19302", _PINNED),
    ]),
    ("rtp", [
        ("nortp_timeout", "15", _PINNED),
        ("rtcp_mux", "1", _PINNED),
        ("avpf", "1", _PINNED),
        ("accept_bundle", "0", _PINNED),
    ]),
    # No video anywhere
    ("video", [
        ("capture", "0", _PINNED),
        ("display", "0", _PINNED),
        ("automatically_initiate", "0", _PINNED),
        ("automatically_accept", "0", _PINNED),
    ]),
    ("misc", [
        # The phone re-downloads [misc] config-uri at every core start
        ("transient_provisioning", "0", _PINNED),
        ("real_early_media", "0", _PINNED),
        ("vibrate_on_incoming_call", "1", _SEEDED),
        # Bootstrap-only entries (config-uri, config-uri-header_0) are added by
        # build_provisioning_config when refresh_url and provisioning_key are passed.
    ]),
    ("app", [
        # A persistent "Linphone is running" notification.
        ("keep_service_alive", "1", _PINNED),
        # Behind hide_advanced_settings, so out of reach, but inbound calls
        # depend on both, which is reason enough to state them.
        ("auto_start", "1", _PINNED),
        # Whether a call is recorded is decided on the provider, never on the
        # handset, and the Calls section offers the switch.
        ("auto_start_call_record", "0", _PINNED),
        ("auto_answer", "0", _SEEDED),
        ("auto_answer_delay", "0", _SEEDED),
    ]),
    ("ui", [
        ("theme_main_color", "plum", _PINNED),
        ("max_account", "1", _PINNED),
        ("hide_sip_addresses", "1", _PINNED),
        ("only_display_sip_uri_username", "1", _PINNED),
        ("contacts_filter", "", _PINNED),  # allows all phone's contacts to be displayed
        ("automatically_show_dialpad", "1", _SEEDED),
        ("show_letters_on_dialpad", "0", _PINNED),
        ("show_past_meetings", "0", _PINNED),
        ("hide_settings", "0", _PINNED),
        ("hide_account_settings", "1", _PINNED),
        ("hide_advanced_settings", "1", _PINNED),
        ("disable_chat_feature", "1", _PINNED),
        ("disable_meetings_feature", "1", _PINNED),
        ("disable_broadcast_feature", "1", _PINNED),
        ("disable_call_recordings_feature", "1", _PINNED),
        ("assistant_hide_create_account", "1", _PINNED),
        ("assistant_hide_third_party_account", "1", _PINNED),
    ]),
    ("auth_info_0", [
        # username, userid, passwd, domain are added by build_provisioning_config.
    ]),
    ("proxy_0", [
        # The account enable/disable switch in the app writes this key. It is
        # stated so a fresh install registers, and only seeded so that a user
        # who turns their account off does not see it turn back on by itself.
        ("reg_sendregister", "1", _SEEDED),
        ("reg_expires", "3600", _PINNED),
        # reg_identity, reg_proxy, reg_route are added by build_provisioning_config.
        ("publish", "0", _PINNED),  # No SIP SUBSCRIBE/PUBLISH
        ("dial_escape_plus", "0", _PINNED),
        ("avpf", "1", _PINNED),
        # Maybe we will implement a push gateway in the future, but for now we disable push.
        ("push_notification_allowed", "0", _PINNED),
        ("remote_push_notification_allowed", "0", _PINNED),
    ]),
]


def _render_provisioning_document(sections):
    """Render the provisioning document as XML.

    Each section is a tuple (section_name, [(key, value, pinned), ...]). Values
    are XML-escaped via markupsafe at emission, so the structure itself cannot
    carry XML-special characters that would break the document. A pinned entry
    gets overwrite="true"; the attribute is omitted otherwise rather than
    written as "false", since liblinphone only ever compares it to "true" and
    omitting it keeps us clear of how lpconfig.xsd declares it.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<config xmlns="http://www.linphone.org/xsds/lpconfig.xsd">')
    for section_name, entries in sections:
        lines.append(f'  <section name="{section_name}">')
        for key, value, pinned in entries:
            overwrite = ' overwrite="true"' if pinned else ''
            lines.append(f'    <entry name="{key}"{overwrite}>{escape(value)}</entry>')
        lines.append('  </section>')
    lines.append('</config>')
    return '\n'.join(lines)


# Control characters would be written verbatim into the phone's linphonerc, whose
# writer emits "key=value\n", and corrupt it.
_SIP_DISPLAY_NAME_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _sip_display_name(name):
    """Make `name` safe inside the SIP quoted-string of ``reg_identity``.

    Control characters would be written verbatim into the phone's ``linphonerc``
    (``key=value\\n``) and corrupt it; ``"`` and ``\\`` would terminate or escape
    the quoted string.
    """
    collapsed = " ".join(_SIP_DISPLAY_NAME_CONTROL_CHARS.sub(" ", name or "").split())
    return collapsed.replace("\\", "\\\\").replace('"', '\\"')


def build_provisioning_config(user_display_name, username, password, domain,
                              refresh_url=None, provisioning_key=None):
    """Render the provisioning document.

    Passing `refresh_url` and `provisioning_key` renders a bootstrap document,
    which additionally provisions [misc] config-uri and the device key header.
    Omitting both renders a refresh document: the phone already holds those two
    keys and transient_provisioning=0 keeps them.
    """
    # Build the full sections list by augmenting the base structure with
    # user-specific entries. auth_info_0 and proxy_0 have placeholder entries
    # in _PROVISIONING_SECTIONS; we replace them with the full dynamic entries.
    sections = []
    for section_name, base_entries in _PROVISIONING_SECTIONS:
        if section_name == "auth_info_0":
            # Every auth_info_N section is wiped before this document is applied,
            # so the credentials have to be restated here.
            entries = [
                ("username", username, _PINNED),
                ("userid", username, _PINNED),
                ("passwd", password, _PINNED),
                ("domain", domain, _PINNED),
            ]
        elif section_name == "proxy_0":
            # reg_identity, reg_proxy, reg_route, reg_expires are user-specific.
            display_name = _sip_display_name(user_display_name)
            entries = [
                ("reg_identity", f'"{display_name}" <sip:{username}@{domain}>', _PINNED),
                ("reg_proxy", f'<sip:{domain};transport=tls>', _PINNED),
                ("reg_route", f'<sip:{domain};transport=tls>', _PINNED),
                *base_entries,
            ]
        elif section_name == "misc" and refresh_url:
            # Bootstrap document: add config-uri and config-uri-header_0.
            key_header = f"{PROVISIONING_KEY_HEADER}:{provisioning_key}"
            entries = [
                *base_entries,
                ("config-uri", refresh_url, _PINNED),
                ("config-uri-header_0", key_header, _PINNED),
            ]
        else:
            entries = base_entries
        sections.append((section_name, entries))
    return _render_provisioning_document(sections)


def new_provisioning_key():
    """Fresh device key.

    ``token_urlsafe`` only yields ``[A-Za-z0-9_-]``: no whitespace and no ``:``,
    so the key is safe both in a single-line config entry and in a header value.
    """
    return secrets.token_urlsafe(32)


def provisioning_key_hash(env, key):
    """Only the digest is stored, so a database read does not yield a usable key.

    Keyed on database.secret rather than a bare digest, so the stored value is
    not verifiable outside the database it belongs to. Its own scope, because
    the key authorises a refresh while PROVISIONING_TOKEN_SCOPE signs the URL
    that carries it.
    """
    return hmac(env(su=True), PROVISIONING_KEY_SCOPE, key)


def is_linphone_provisioning_request(headers):
    """Whether the request looks like a liblinphone provisioning fetch.

    liblinphone always sends `X-Linphone-Provisioning: 1`
    (remote_provisioning.c) and a User-Agent built by
    linphone_core_get_user_agent(), which contains "Linphone" on every
    official client (LinphoneAndroid/…, LinphoneiOS/…, … LinphoneSDK/…).
    """
    if not headers.get("X-Linphone-Provisioning"):
        return False
    return "linphone" in (headers.get("User-Agent") or "").lower()
