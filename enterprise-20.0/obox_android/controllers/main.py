from odoo import fields, http

from odoo.addons.obox.controllers.main import OboxController, _check_obox_access


class OboxAndroidController(OboxController):
    @http.route()
    def obox_connect(self, serial_number, token, local_ip, services, local_port=0, name=None, platform=None):
        box = _check_obox_access(serial_number, token)
        box.local_port = local_port or 0
        if platform in dict(box._fields["platform"].selection):
            box.platform = platform
        if name and box.state == "01_pairing":
            box.with_context(obox_sync=True).name = name
        super().obox_connect(serial_number, token, local_ip, services)
        return box._config_response() if box.supports_sync else None

    @http.route("/obox/sync", auth="public", type="jsonrpc")
    def obox_sync(self, serial_number, token, state=None, full=False):
        box = _check_obox_access(serial_number, token)
        box._sync_device_state(state or {}, full=full)
        return box._config_response()

    @http.route("/obox/feature", auth="public", type="jsonrpc")
    def obox_feature_detail(self, serial_number, token, name):
        box = _check_obox_access(serial_number, token)
        return box._get_obox_feature_details(name) if name else {}

    @http.route("/obox/screenshot", auth="public", type="jsonrpc")
    def obox_screenshot(self, serial_number, token, screenshot=None):
        box = _check_obox_access(serial_number, token)
        if screenshot:
            box.sudo().write({
                "screenshot": screenshot,
                "screenshot_date": fields.Datetime.now(),
            })
            box._send_obox_updated_notification()

    @http.route("/obox/logs", auth="public", type="jsonrpc")
    def obox_logs(self, serial_number, token, logs=None):
        box = _check_obox_access(serial_number, token)
        if logs:
            box.sudo().write({
                "log_file": logs,
                "log_file_date": fields.Datetime.now(),
            })
            box._send_obox_updated_notification()
