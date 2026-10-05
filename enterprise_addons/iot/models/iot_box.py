import logging
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from odoo import api, fields, models
from odoo.http import request
from odoo.tools import consteq

_logger = logging.getLogger(__name__)


class IotBox(models.Model):
    _name = 'iot.box'
    _description = 'IoT Box'

    name = fields.Char('Name', required=True)
    identifier = fields.Char(string='Identifier', readonly=True)
    device_ids = fields.One2many('iot.device', 'iot_id', string="Devices")
    device_count = fields.Integer(compute='_compute_device_count')
    ip = fields.Char('Domain Address', readonly=True)
    use_custom_handlers = fields.Boolean(help="Download custom handlers from the database", default=False)
    version = fields.Char('Image Version', readonly=True)
    version_commit_url = fields.Html(readonly=True, compute='_compute_commit_url')
    company_id = fields.Many2one('res.company', 'Company')
    ssl_certificate_end_date = fields.Datetime('SSL Certificate End Date', readonly=True)
    token = fields.Char(readonly=True)
    use_lna = fields.Boolean(string="Use Local Network Access")

    def _compute_device_count(self):
        for box in self:
            box.device_count = len(box.device_ids)

    @api.ondelete(at_uninstall=True)
    def _unlink_iot_box(self):
        for identifier in self.mapped('identifier'):
            self.env['iot.channel'].send_message({
                "iot_identifier": identifier
            }, 'server_clear')

    def open_homepage(self):
        self.ensure_one()
        scheme = urlsplit(request.httprequest.referrer).scheme
        return {
            'type': 'ir.actions.act_url',
            'url': f'{scheme}://{self.ip}' if scheme == 'https' else f'{scheme}://{self.ip}:8069',
            'target': 'new',
        }

    @api.model
    def connect_iot_box(self, local_iot_boxes: list[dict[str, str]]):
        """
        This method is called when pressing the "Connect" button in the IoT app.
        Used to connect a new IoT Box to a database.
        :return: action to open the wizard view depending on the result of the iot-proxy request sent by the wizard
        """
        wizard = self.env['add.iot.box'].create([{'token': secrets.token_hex(16)}])
        self.env['iot.discovered.box'].create([
            {
                "pairing_code": box["pairing_code"],
                "serial_number": box.get("serial_number"),
                "add_iot_box_wizard_id": wizard.id,
            }
            for box in local_iot_boxes
        ])
        return wizard.add_iot_box_wizard_action()

    @api.model
    def _get_by_token(self, token: str):
        if not token:
            raise ValueError("Token must be provided")
        return next((
            box for box in self.env['iot.box'].sudo().search([('token', '!=', False)])
            if consteq(box.token, token)
        ), None)

    @api.depends('version')
    def _compute_commit_url(self):
        base_url = "https://www.github.com/odoo/odoo/commit/"
        for box in self:
            if box.version and "#" in box.version:
                image_version, commit_hash = box.version.split("#", 1)
                box.version_commit_url = (
                    f'<span>{image_version}#<a href="{base_url}{commit_hash}" target="_blank">{commit_hash}</a></span>'
                )
            else:
                box.version_commit_url = f'<span>{box.version}</span>' if box.version else False

    @api.autovacuum
    def _cleanup_drafts_cron(self):
        """Delete draft iot.box records (without identifier).
        Draft records are created when starting the pairing process,
        and are named "Connecting...".
        """
        timeout_date = fields.Datetime.now() - timedelta(hours=1)
        self.search([
            ("identifier", "=", False),
            ('name', '=ilike', 'Connecting%'),
            ("create_date", "<", timeout_date),
        ]).unlink()

    @api.onchange("use_custom_handlers")
    def _onchange_use_custom_drivers(self):
        for box in self:
            self.env["iot.channel"].send_message({
                "iot_identifier": box.identifier,
                "use_custom_handlers": box.use_custom_handlers
            }, "toggle_custom_handlers")
