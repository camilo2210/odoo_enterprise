# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import uuid


class L10nDePosTssExport(models.Model):
    _name = 'l10n_de_pos.tss_export'
    _description = 'TSS export request for audit data retrieval.'

    config_id = fields.Many2one(
        comodel_name='pos.config',
        string="Point of Sale",
        required=True,
        domain="[('l10n_de_fiskaly_tss_id', '!=', False), ('l10n_de_fiskaly_client_id', '!=', False)]",
        help="Select a point of sale linked to a TSS.")
    l10n_de_fiskaly_export_uuid = fields.Char(
        string="Export UUID",
        readonly=True,
        copy=False,
        default=lambda self: str(uuid.uuid4()),
        help="The UUID of the export in the Fiskaly service.")
    start_datetime = fields.Datetime(
        string="Start Datetime",
        required=True,
        help="Export data with dates greater than or equal to this datetime.")
    end_datetime = fields.Datetime(
        string="End Datetime",
        required=True,
        help="Export data with dates less than or equal to this datetime.")
    state = fields.Selection(
        selection=[
            ('pending', "Pending"),
            ('working', "Working"),
            ('completed', "Completed"),
            ('cancelled', "Cancelled"),
            ('error', "Error"),
        ],
        string="State",
        readonly=True,
    )
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)

    @api.constrains('start_datetime', 'end_datetime')
    def _check_datetime(self):
        for export in self:
            if export.start_datetime > export.end_datetime:
                raise ValidationError(_('The start datetime must be earlier than the end datetime.'))

    @api.model_create_multi
    def create(self, vals_list):
        exports = super().create(vals_list)
        for export in exports:
            export._l10n_de_trigger_fiskaly_export()
        return exports

    def _l10n_de_trigger_fiskaly_export(self):
        self.ensure_one()
        payload = {
            'start_date': self.start_datetime.timestamp(),
            'end_date': self.end_datetime.timestamp(),
            'client_id': self.config_id.l10n_de_fiskaly_client_id,
        }
        tss_id = self.config_id._l10n_de_get_tss_id()
        trigger_resp = self.company_id._l10n_de_fiskaly_kassensichv_rpc(
            'PUT',
            f'/tss/{tss_id}/export/{self.l10n_de_fiskaly_export_uuid}',
            payload,
        )

        if trigger_resp.status_code == 404:
            raise ValidationError(_(
                'No transaction data is available for the selected datetime range and point of sale.'
            ))
        trigger_resp.raise_for_status()
        self.state = trigger_resp.json().get('state', self.state).lower()

    def l10n_de_action_refresh_state(self):
        self.ensure_one()
        tss_id = self.config_id._l10n_de_get_tss_id()
        export_res = self.company_id._l10n_de_fiskaly_kassensichv_rpc(
            'GET',
            f'/tss/{tss_id}/export/{self.l10n_de_fiskaly_export_uuid}',
        )
        export_res.raise_for_status()
        export_data = export_res.json()
        self.state = export_data.get('state', self.state).lower()

    def l10n_de_action_download_export(self):
        """
        Download the TSS export from Fiskaly.
        https://workspace.fiskaly.com/api/sign-de/#operation/retrieveExportFile
        """
        self.ensure_one()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'l10n_de_pos.tss_export'),
            ('res_id', '=', self.id),
        ], limit=1)
        if not attachment:
            tss_id = self.config_id._l10n_de_get_tss_id()
            download_resp = self.company_id._l10n_de_fiskaly_kassensichv_rpc(
                'GET',
                f'/tss/{tss_id}/export/{self.l10n_de_fiskaly_export_uuid}/file',
            )
            download_resp.raise_for_status()
            attachment = self.env['ir.attachment'].create({
                'name': (
                    'tss-%s-%s.tar' % (
                        self.start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                        self.end_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    )
                ),
                'raw': download_resp.content,
                'res_model': 'l10n_de_pos.tss_export',
                'res_id': self.id,
            })
        return {
            'target': 'new',
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=1',
        }
