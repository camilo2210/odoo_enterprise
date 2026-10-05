import xml.etree.ElementTree as ET
from http import HTTPStatus
from urllib.parse import urlsplit

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.voip.tools.linphone import (
    PROVISIONING_KEY_HEADER,
    PROVISIONING_MAX_DEVICES,
    build_provisioning_config,
)

from .common_voip import VoipPhoneServiceCase

LINPHONE_HEADERS = {
    "X-Linphone-Provisioning": "1",
    "User-Agent": "LinphoneAndroid/6.0 (Pixel) LinphoneSDK/5.4",
}
LPCONFIG_NS = "{http://www.linphone.org/xsds/lpconfig.xsd}"
REFRESH_URL = "https://odoo.example.com/voip/linphone_provisioning/tok"
# Sections and keys the document deletes on purpose, by sending them empty.
DELETED_ENTRIES = {("ui", "contacts_filter")}


def _entries(document, section):
    root = ET.fromstring(document)
    return {
        entry.get("name"): entry.text
        for entry in root.find(f"{LPCONFIG_NS}section[@name='{section}']")
    }


@tagged("voip", "post_install", "-at_install")
class TestLinphoneProvisioningDocument(TransactionCase):
    def test_display_name_cannot_break_out_of_the_sip_quoted_string(self):
        # A raw quote would terminate the quoted-string early and a newline would
        # be written verbatim into the phone's linphonerc (key=value\n).
        document = build_provisioning_config(
            user_display_name='Jean "Le Boss" Dupont\nX',
            username="jdupont",
            password="s3cr3t",
            domain="pbx.example.com",
        )
        self.assertEqual(
            _entries(document, "proxy_0")["reg_identity"],
            r'"Jean \"Le Boss\" Dupont X" <sip:jdupont@pbx.example.com>',
        )

    def test_every_entry_value_stays_writable_to_linphonerc(self):
        # liblinphone takes the raw first child node as the value and rewrites it
        # as "key=value\n": leading/trailing whitespace or a newline corrupts the
        # phone's configuration file, and an empty value deletes the key. The
        # bootstrap variant carries the most entries.
        document = build_provisioning_config(
            user_display_name="Bernard Bernoulli",
            username="bbernoulli",
            password="s3cr3t",
            domain="pbx.example.com",
            refresh_url=REFRESH_URL,
            provisioning_key="k3y",
        )
        offenders = [
            (section.get("name"), entry.get("name"), repr(entry.text))
            for section in ET.fromstring(document)
            for entry in section
            if (section.get("name"), entry.get("name")) not in DELETED_ENTRIES
            and (not entry.text or entry.text != entry.text.strip() or "\n" in entry.text)
        ]
        self.assertEqual(offenders, [])

    def test_provisioned_phones_list_the_whole_address_book(self):
        # The rc shipped with the app filters the contact list on
        # sip.linphone.org and the app narrows that to SIP addresses only for an
        # account on any other domain, so the filter has to be taken back to its
        # built-in default - and the only way to do that from a provisioning
        # document is an empty value, which liblinphone turns into a deletion.
        document = build_provisioning_config(
            user_display_name="Bernard Bernoulli",
            username="bbernoulli",
            password="s3cr3t",
            domain="pbx.example.com",
        )
        entry = ET.fromstring(document).find(
            f"{LPCONFIG_NS}section[@name='ui']/{LPCONFIG_NS}entry[@name='contacts_filter']",
        )
        self.assertIsNone(entry.text)
        # A phone that narrowed the list has no way back: hide_sip_addresses
        # hides the filter chip, so the deletion must be restated every time.
        self.assertEqual(entry.get("overwrite"), "true")

    def test_bootstrap_document_installs_the_refresh_credential(self):
        document = build_provisioning_config(
            user_display_name="Bernard Bernoulli",
            username="bbernoulli",
            password="s3cr3t",
            domain="pbx.example.com",
            refresh_url=REFRESH_URL,
            provisioning_key="k3y",
        )
        misc = _entries(document, "misc")
        self.assertEqual(misc["transient_provisioning"], "0")
        self.assertEqual(misc["config-uri"], REFRESH_URL)
        # No space after the colon: liblinphone splits the entry at the first
        # colon and forwards the rest of the string verbatim as the header value.
        self.assertEqual(misc["config-uri-header_0"], f"{PROVISIONING_KEY_HEADER}:k3y")

    def test_refresh_document_omits_the_bootstrap_entries(self):
        document = build_provisioning_config(
            user_display_name="Bernard Bernoulli",
            username="bbernoulli",
            password="s3cr3t",
            domain="pbx.example.com",
        )
        misc = _entries(document, "misc")
        self.assertNotIn("config-uri", misc)
        self.assertNotIn("config-uri-header_0", misc)
        # Every applied document must restate the credentials: liblinphone prunes
        # all auth_info_N sections before applying one.
        self.assertEqual(_entries(document, "auth_info_0")["passwd"], "s3cr3t")

    def test_the_settings_the_app_exposes_are_not_overwritten(self):
        # The phone re-applies this document at every core start, and
        # liblinphone keeps the value it already holds unless the entry carries
        # overwrite="true" (xml2lpc.c, processEntry). A setting the open
        # settings screen lets the user change must therefore be seeded, or
        # their choice is silently undone at the next launch; a requirement of
        # the platform must stay pinned, or a phone can drift away from it for
        # good.
        document = build_provisioning_config(
            user_display_name="Bernard Bernoulli",
            username="bbernoulli",
            password="s3cr3t",
            domain="pbx.example.com",
            refresh_url=REFRESH_URL,
            provisioning_key="k3y",
        )
        entries = [
            (section.get("name"), entry.get("name"), entry.get("overwrite"))
            for section in ET.fromstring(document)
            for entry in section
        ]
        user_owned = {
            ("proxy_0", "reg_sendregister"),  # the account "Connected" toggle
            ("ui", "automatically_show_dialpad"),
            ("misc", "vibrate_on_incoming_call"),
            ("app", "auto_answer"),
            ("app", "auto_answer_delay"),
            ("net", "wifi_only"),
        }
        ours = {
            ("sip", "media_encryption"),
            ("sip", "media_encryption_mandatory"),
            ("ui", "hide_account_settings"),
            ("ui", "hide_advanced_settings"),
            ("misc", "config-uri"),
            ("auth_info_0", "passwd"),
        }
        # A renamed or dropped key would otherwise pass both assertions below.
        self.assertEqual((user_owned | ours) - {key[:2] for key in entries}, set())
        pinned = {key[:2] for key in entries if key[2] == "true"}
        self.assertEqual(pinned & user_owned, set())
        self.assertEqual(ours - pinned, set())

    def test_served_document_carries_no_xml_comments(self):
        # The rationale lives in XML comments in the source template; the phone
        # must never receive them - transient_provisioning=0 means that payload
        # is re-fetched by every provisioned phone at every app launch.
        document = build_provisioning_config(
            user_display_name="Bernard Bernoulli",
            username="bbernoulli",
            password="s3cr3t",
            domain="pbx.example.com",
            refresh_url=REFRESH_URL,
            provisioning_key="k3y",
        )
        self.assertNotIn("<!--", document)
        self.assertNotIn("-->", document)


@tagged("voip", "post_install", "-at_install")
class TestLinphoneProvisioningRoute(VoipPhoneServiceCase):
    def setUp(self):
        super().setUp()
        self.user = self.new_voip_user()
        self.settings = self.user.res_users_settings_id
        if not self.user.uses_odoo_provider:
            self.settings.sudo().with_context(voip_skip_pbx_sync=True).voip_provider_id = (
                self.env["voip.pbx.service"].voip_provider
            )
        self.assertTrue(self.user.uses_odoo_provider)

    def _provisioning_path(self):
        # _get_linphone_provisioning_url() builds an absolute URL from
        # web.base.url, which is not the test server: keep the path only.
        return urlsplit(self.user.with_user(self.user)._get_linphone_provisioning_url()).path

    def _serial(self):
        self.settings.invalidate_recordset(["voip_linphone_provisioning_serial"])
        return self.settings.voip_linphone_provisioning_serial

    def _key_hashes(self):
        self.settings.invalidate_recordset(["voip_linphone_provisioning_key_hashes"])
        return self.settings.voip_linphone_provisioning_key_hashes or []

    def _bootstrap(self):
        """Consume a QR code and return the refresh path and the device key."""
        response = self.url_open(self._provisioning_path(), headers=LINPHONE_HEADERS)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        misc = _entries(response.text, "misc")
        name, _, key = misc["config-uri-header_0"].partition(":")
        self.assertEqual(name, PROVISIONING_KEY_HEADER)
        return urlsplit(misc["config-uri"]).path, key

    def _refresh(self, path, key=None):
        headers = dict(LINPHONE_HEADERS)
        if key is not None:
            headers[PROVISIONING_KEY_HEADER] = key
        return self.url_open(path, headers=headers)

    @mute_logger("odoo.addons.voip.controllers.voip_controller")
    def test_route_only_answers_a_linphone_client(self):
        path = self._provisioning_path()
        for headers in (
            None,
            {"X-Linphone-Provisioning": "1"},
            {"User-Agent": "LinphoneAndroid/6.0"},
            {"X-Linphone-Provisioning": "1", "User-Agent": "curl/8.5.0"},
        ):
            response = self.url_open(path, headers=headers)
            self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND, headers)
        # A refused request must not burn the QR code.
        self.assertEqual(self._serial(), 0)
        response = self.url_open(path, headers=LINPHONE_HEADERS)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.headers["Content-Type"], "application/xml")

    @mute_logger("odoo.addons.voip.controllers.voip_controller")
    def test_serving_a_document_invalidates_the_token(self):
        path = self._provisioning_path()
        self.assertEqual(
            self.url_open(path, headers=LINPHONE_HEADERS).status_code,
            HTTPStatus.OK,
        )
        self.assertEqual(self._serial(), 1)
        # Same URL, same headers: the serial signed into the QR code is stale now.
        self.assertEqual(
            self.url_open(path, headers=LINPHONE_HEADERS).status_code,
            HTTPStatus.NOT_FOUND,
        )
        # A freshly minted QR code carries the new serial and is served once more.
        self.assertEqual(
            self.url_open(self._provisioning_path(), headers=LINPHONE_HEADERS).status_code,
            HTTPStatus.OK,
        )
        self.assertEqual(self._serial(), 2)

    @mute_logger("odoo.addons.voip.controllers.voip_controller")
    def test_refresh_requires_the_device_key(self):
        path, key = self._bootstrap()
        self.assertEqual(self._refresh(path).status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(self._refresh(path, "wrong").status_code, HTTPStatus.NOT_FOUND)
        # Right key, but not a Linphone client.
        self.assertEqual(
            self.url_open(path, headers={PROVISIONING_KEY_HEADER: key}).status_code,
            HTTPStatus.NOT_FOUND,
        )
        self.assertEqual(self._refresh(path, key).status_code, HTTPStatus.OK)

    @mute_logger("odoo.addons.voip.controllers.voip_controller")
    def test_refresh_is_idempotent(self):
        path, key = self._bootstrap()
        serial = self._serial()
        for _ in range(3):
            response = self._refresh(path, key)
            self.assertEqual(response.status_code, HTTPStatus.OK)
        # Refreshing consumes nothing, and the phone already holds config-uri.
        self.assertEqual(self._serial(), serial)
        misc = _entries(response.text, "misc")
        self.assertNotIn("config-uri", misc)
        self.assertNotIn("config-uri-header_0", misc)

    @mute_logger("odoo.addons.voip.controllers.voip_controller")
    def test_a_second_bootstrap_provisions_a_second_phone(self):
        path_a, key_a = self._bootstrap()
        path_b, key_b = self._bootstrap()
        self.assertNotEqual(key_a, key_b)
        # Every phone of a user shares one refresh URL and is told apart by its key.
        self.assertEqual(path_a, path_b)
        self.assertEqual(len(self._key_hashes()), 2)
        self.assertEqual(self._refresh(path_a, key_a).status_code, HTTPStatus.OK)
        self.assertEqual(self._refresh(path_b, key_b).status_code, HTTPStatus.OK)

    @mute_logger("odoo.addons.voip.controllers.voip_controller")
    def test_oldest_device_falls_off_the_cap(self):
        path, first_key = self._bootstrap()
        for _ in range(PROVISIONING_MAX_DEVICES):
            _, last_key = self._bootstrap()
        self.assertEqual(len(self._key_hashes()), PROVISIONING_MAX_DEVICES)
        self.assertEqual(self._refresh(path, first_key).status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(self._refresh(path, last_key).status_code, HTTPStatus.OK)

    @mute_logger("odoo.addons.voip.controllers.voip_controller")
    def test_refresh_rejected_when_no_phone_is_provisioned(self):
        path, key = self._bootstrap()
        self.settings.sudo().voip_linphone_provisioning_key_hashes = []
        self.assertEqual(self._refresh(path, key).status_code, HTTPStatus.NOT_FOUND)

    @mute_logger("odoo.addons.voip.controllers.voip_controller")
    def test_refresh_key_is_isolated_per_user(self):
        # The refresh route is auth="public" and relies on the signed user_id in
        # the token plus the per-user digest list. A key provisioned on user B
        # must not work on user A's refresh URL, or the isolation is broken.
        path_a, _key_a = self._bootstrap()
        other = self.new_voip_user(phone="+3281234568", user_login="other_voip_user")
        other_settings = other.res_users_settings_id
        other_settings.sudo().with_context(voip_skip_pbx_sync=True).voip_provider_id = (
            self.env["voip.pbx.service"].voip_provider
        )
        other_path = urlsplit(other.with_user(other)._get_linphone_provisioning_url()).path
        other_response = self.url_open(other_path, headers=LINPHONE_HEADERS)
        self.assertEqual(other_response.status_code, HTTPStatus.OK)
        other_key = _entries(other_response.text, "misc")["config-uri-header_0"].split(":", 1)[1]
        self.assertEqual(self._refresh(path_a, other_key).status_code, HTTPStatus.NOT_FOUND)

    def test_only_a_consumed_code_notifies_its_owner(self):
        # A form left open still shows the code and the link this very request
        # invalidates, so the browser has to hear about it.
        notifications = self.env["bus.bus"].sudo()
        domain = [("message", "like", "linphone_provisioning/rotated")]
        self.assertFalse(notifications.search(domain))

        path, key = self._bootstrap()
        notification = notifications.search(domain)
        self.assertEqual(len(notification), 1)
        # Anyone else's browser would be told to re-read a code that is none of
        # their business and did not change.
        self.assertIn('"res.users"', notification.channel)
        self.assertIn(str(self.user.id), notification.channel)

        # A refresh fetch leaves the serial alone: the code on screen is still
        # the one a new phone would have to read.
        self.assertEqual(self._refresh(path, key).status_code, HTTPStatus.OK)
        self.assertEqual(notifications.search(domain), notification)
