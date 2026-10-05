import hashlib
import json
import secrets
from datetime import UTC, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import human_size

# Writing any of these fields trigger a box sync
_CONFIG_FIELDS = frozenset({"kiosk_pin", "name"})


class OboxObox(models.Model):
    _inherit = "obox.obox"

    local_port = fields.Integer(string="Web Server Port", readonly=True)
    local_address = fields.Char(string="Local address", compute="_compute_local_address", readonly=True)
    platform = fields.Selection(
        [("rpi", "Raspberry Pi"), ("android", "Android"), ("windows", "windows")],
        string="Platform",
        default="rpi",
        required=True,
        readonly=True,
    )
    is_android = fields.Boolean(compute="_compute_is_android")
    supports_sync = fields.Boolean(store=True, compute="_compute_supports_sync")
    supports_kiosk = fields.Boolean(store=True, compute="_compute_supports_kiosk")
    device_state = fields.Json(string="Device State", default=dict, readonly=True)
    device_state_date = fields.Datetime(string="Last State Update", readonly=True)
    screenshot = fields.Binary(string="Screenshot", readonly=True)
    screenshot_date = fields.Datetime(string="Screenshot Date", readonly=True)
    log_file = fields.Binary(string="Log File", attachment=True, readonly=True)
    log_file_name = fields.Char(compute="_compute_log_file_name")
    log_file_date = fields.Datetime(string="Log File Date", readonly=True)
    kiosk_pin = fields.Char(string="Kiosk PIN", copy=False)
    has_kiosk_pin = fields.Boolean(compute="_compute_has_kiosk_pin")
    config = fields.Json(string="Configuration", compute="_compute_config")
    config_version = fields.Char(string="Configuration Version", compute="_compute_config_version")
    config_synced = fields.Boolean(string="Configuration Applied", compute="_compute_config_synced")

    android_id = fields.Char(string="Android ID", compute="_compute_android_info")
    android_app_version = fields.Char(string="App Version", compute="_compute_android_info")
    android_model = fields.Char(string="Model", compute="_compute_android_info")
    android_manufacturer = fields.Char(string="Manufacturer", compute="_compute_android_info")
    android_processor = fields.Char(string="Processor", compute="_compute_android_info")
    android_version = fields.Char(string="Android Version", compute="_compute_android_info")
    android_locale = fields.Char(string="Locale", compute="_compute_android_info")
    android_timezone = fields.Char(string="Timezone", compute="_compute_android_info")
    android_uptime = fields.Datetime(string="Up Since", compute="_compute_android_info")
    android_is_device_owner = fields.Boolean(string="Device Owner", compute="_compute_android_info")
    android_locked_by_admin = fields.Boolean(string="Screen Locked", compute="_compute_android_info")
    android_kiosk_enabled = fields.Boolean(string="Kiosk Mode", compute="_compute_android_info")
    android_network_type = fields.Char(string="Network", compute="_compute_android_info")
    android_is_wifi = fields.Boolean(compute="_compute_android_info")
    android_wifi_ssid = fields.Char(string="WiFi SSID", compute="_compute_android_info")
    android_signal_level = fields.Integer(string="Signal (0-4)", compute="_compute_android_info")
    android_screen_on = fields.Boolean(string="Screen On", compute="_compute_android_info")
    android_brightness = fields.Integer(string="Brightness", compute="_compute_android_info")
    android_resolution = fields.Char(string="Resolution", compute="_compute_android_info")
    android_audio_volume = fields.Integer(string="Volume", compute="_compute_android_info")
    android_battery_level = fields.Integer(string="Battery (%)", compute="_compute_android_info")
    android_battery_charging = fields.Boolean(string="Charging", compute="_compute_android_info")
    android_battery_plugged = fields.Boolean(string="Plugged In", compute="_compute_android_info")
    android_memory_used = fields.Char(string="Memory Used", compute="_compute_android_info")
    android_memory_total = fields.Char(string="Memory Total", compute="_compute_android_info")
    android_storage_used = fields.Char(string="Storage Used", compute="_compute_android_info")
    android_storage_total = fields.Char(string="Storage Total", compute="_compute_android_info")
    android_webview_provider = fields.Char(string="WebView", compute="_compute_android_info")
    android_webview_version = fields.Char(string="WebView Version", compute="_compute_android_info")
    android_webview_ua = fields.Char(string="User Agent", compute="_compute_android_info")

    @api.depends("platform")
    def _compute_is_android(self):
        for record in self:
            record.is_android = record.platform == "android"

    @api.depends("services")
    def _compute_supports_sync(self):
        for record in self:
            record.supports_sync = "sync" in (record.services or [])

    @api.depends('services')
    def _compute_supports_kiosk(self):
        for record in self:
            record.supports_kiosk = 'kiosk' in (record.services or [])

    def _compute_local_address(self):
        for record in self:
            if not record.local_ip:
                record.local_address = False
            elif not record.local_port or record.local_port == 80:
                record.local_address = f"{record.local_ip}"
            else:
                record.local_address = f"{record.local_ip}:{record.local_port}"

    @api.depends("serial_number", "log_file_date")
    def _compute_log_file_name(self):
        for record in self:
            stamp = record.log_file_date and record.log_file_date.strftime("%Y%m%d-%H%M%S")
            record.log_file_name = f"obox-logs-{stamp}.zip" if stamp else "obox-logs.zip"

    def _get_obox_features(self):
        self.ensure_one()
        return []

    def _get_obox_feature_details(self, name):
        return {}

    @api.depends("kiosk_pin")
    def _compute_has_kiosk_pin(self):
        for record in self:
            record.has_kiosk_pin = bool(record.kiosk_pin)

    @api.depends("kiosk_pin", "name", "device_ids.name")
    def _compute_config(self):
        for record in self:
            record.config = {
                "name": record.name or "",
                "kiosk_pin": record.kiosk_pin or "",
                "features": record._get_obox_features(),
                "devices": [
                    {"identifier": device.identifier, "name": device.name}
                    for device in record.device_ids.sorted("identifier")
                ],
            }

    @api.depends("config")
    def _compute_config_version(self):
        for record in self:
            payload = json.dumps(record.config or {}, sort_keys=True)
            record.config_version = hashlib.sha256(payload.encode()).hexdigest()

    @api.depends("config_version", "device_state")
    def _compute_config_synced(self):
        for record in self:
            applied = (record.device_state or {}).get("config_version")
            record.config_synced = bool(applied) and applied == record.config_version

    def _sync_device_state(self, state, full=False):
        self.ensure_one()
        state = dict(state or {})
        devices = state.pop("devices", None)

        stored = {} if full else dict(self.device_state or {})
        stored.update(state)
        vals = {
            "device_state": stored,
            "device_state_date": fields.Datetime.now(),
        }
        if state.get("ip"):
            vals["local_ip"] = state["ip"]
        if state.get("local_port"):
            vals["local_port"] = state["local_port"]

        # Only update the kiosk PIN and name if the config is up to date (avoid overwriting changes made in Odoo).
        up_to_date = state.get("config_version") == self.config_version
        reported_pin = ((state.get("kiosk") or {}).get("kiosk_pin") or "").strip()
        if reported_pin and reported_pin != self.kiosk_pin and (not self.kiosk_pin or up_to_date):
            vals["kiosk_pin"] = reported_pin
        reported_name = (state.get("name") or "").strip()
        if reported_name and reported_name != self.name and up_to_date:
            vals["name"] = reported_name

        self.with_context(obox_sync=True).write(vals)

        if isinstance(devices, dict):
            self._sync_devices(devices.get("added"), trust_name=up_to_date)

        self._send_obox_updated_notification()

    def _config_response(self):
        self.ensure_one()
        response = {"config_up_to_date": self.config_synced}
        if not self.config_synced:
            response["config"] = self.config
            response["config_version"] = self.config_version
        return response

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("obox_sync") and not _CONFIG_FIELDS.isdisjoint(vals):
            for record in self:
                if record.supports_sync:
                    record._request_sync()
        return res

    def _discover_devices_on_connect(self):
        # A box that syncs pushes its devices itself.
        return super()._discover_devices_on_connect() and not self.supports_sync

    def _command_sent_notification(self):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": _("Command sent to the device"),
                "type": "success",
                "sticky": False,
            },
        }

    def _request_sync(self):
        self.ensure_one()
        # Keep only one `request_sync` action queued at a time. We could enforce this
        # with OboxQueue's unique-activity constraint, but that would raise an error
        # when, for example, renaming two devices triggers two sync requests.
        waiting = self.env["obox.queue"].search([
            ("obox_id", "=", self.id),
            ("action_type", "=", "request_sync"),
            ("status", "!=", "done"),
        ], limit=1)
        return waiting or self._queue_action("request_sync", "/odoo/sync")

    def action_sync_obox(self):
        self.ensure_one()
        self._request_sync()
        return self._command_sent_notification()

    def action_request_screenshot(self):
        self.ensure_one()
        self._queue_action("screenshot", "/odoo/screenshot")
        return self._command_sent_notification()

    def action_request_logs(self):
        self.ensure_one()
        self._queue_action("logs", "/odoo/logs")
        return self._command_sent_notification()

    def _open_kiosk(self, config):
        for record in self:
            record._queue_action("open_kiosk", "/odoo/open_kiosk", {
                "url": config.get_kiosk_url(),
                "timezone": config.company_id.tz,
            })

    def action_kiosk_reload(self):
        self.ensure_one()
        self._queue_action("kiosk_reload", "/odoo/kiosk_reload")
        return self._command_sent_notification()

    def action_kiosk_lock_screen(self):
        self.ensure_one()
        self._queue_action("kiosk_screen_lock", "/odoo/kiosk_screen_lock", {"locked": True})
        return self._command_sent_notification()

    def action_kiosk_unlock_screen(self):
        self.ensure_one()
        self._queue_action("kiosk_screen_lock", "/odoo/kiosk_screen_lock", {"locked": False})
        return self._command_sent_notification()

    def action_open_kiosk_pin_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Kiosk PIN"),
            "res_model": "obox.kiosk.pin.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_obox_id": self.id},
        }

    @api.model
    def pair_mobile_obox(self, serial_number, platform=None, name=None):
        """Pair the Mobile device directly from Odoo.
        The mobile app calls this with the session of the logged-in user so no pairing code is required.
        """
        if not serial_number or not serial_number.strip():
            raise UserError(_("A serial number is required to pair a device."))
        token = secrets.token_hex()
        values = {}
        if platform:
            values["platform"] = platform
        if name:
            values["name"] = name
        obox = self._pair_serial_number(serial_number, token, **values)
        return {"id": obox.id, "url": obox.get_base_url(), "token": token}

    @api.depends("device_state")
    def _compute_android_info(self):
        for record in self:
            state = record.device_state or {}
            kiosk = state.get("kiosk") or {}
            network = state.get("network") or {}
            metrics = state.get("metrics") or {}
            hardware = state.get("hardware") or {}
            battery = metrics.get("battery") or {}
            memory = metrics.get("memory") or {}
            storage = metrics.get("storage") or {}
            webview = hardware.get("webview") or {}

            record.android_id = hardware.get("android_id") or False
            record.android_app_version = hardware.get("version") or False
            record.android_model = hardware.get("model") or False
            record.android_manufacturer = hardware.get("manufacturer") or False
            record.android_processor = hardware.get("processor") or False
            record.android_version = (
                "%(version)s (API %(api)s, build %(build)s)" % {
                    "version": hardware.get("android_version"),
                    "api": hardware.get("api_level") or "?",
                    "build": hardware.get("android_build") or "?",
                } if hardware.get("android_version") else False
            )
            record.android_locale = state.get("locale") or False
            record.android_timezone = state.get("timezone") or False
            up_since = metrics.get("up_since")
            record.android_uptime = datetime.fromtimestamp(up_since, UTC).replace(tzinfo=None) if up_since else False
            record.android_is_device_owner = bool(state.get("is_device_owner"))
            record.android_locked_by_admin = bool(kiosk.get("out_of_service"))
            record.android_kiosk_enabled = bool(kiosk.get("enabled"))

            record.android_is_wifi = bool(network.get("wifi"))
            record.android_network_type = (
                _("WiFi") if network.get("wifi")
                else _("Ethernet") if network.get("ethernet")
                else False
            )
            record.android_wifi_ssid = network.get("ssid") if network.get("wifi") else False
            record.android_signal_level = (
                metrics.get("signal_level") if network.get("wifi") else False
            )

            record.android_screen_on = bool(metrics.get("screen_on"))
            record.android_brightness = metrics.get("brightness") or False
            record.android_resolution = hardware.get("resolution") or False
            record.android_audio_volume = metrics.get("volume") or False

            record.android_battery_level = battery.get("level") or False
            record.android_battery_charging = bool(battery.get("charging"))
            record.android_battery_plugged = bool(battery.get("plugged"))

            record.android_memory_used = human_size(memory.get("used")) if memory.get("used") else False
            record.android_memory_total = human_size(memory.get("total")) if memory.get("total") else False
            record.android_storage_used = human_size(storage.get("used")) if storage.get("used") else False
            record.android_storage_total = human_size(storage.get("total")) if storage.get("total") else False

            record.android_webview_provider = webview.get("provider") or False
            record.android_webview_version = webview.get("version") or False
            record.android_webview_ua = webview.get("ua") or False
