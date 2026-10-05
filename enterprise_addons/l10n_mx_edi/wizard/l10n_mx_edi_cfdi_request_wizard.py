from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_cfdi_request import (
    RECEIPT_TYPE_DESCRIPTION,
    RECEIPT_TYPE_SELECTION,
    REQUEST_TYPE_DESCRIPTION,
    REQUEST_TYPE_SELECTION,
)


class L10n_Mx_EdiCfdiRequestWizard(models.TransientModel):
    _name = "l10n_mx_edi.cfdi.request.wizard"
    _description = "Create and send a new CFDI Request"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True, readonly=True,
        default=lambda self: self.env.company,
    )

    request_type = fields.Selection(
        selection=list(REQUEST_TYPE_SELECTION),
        required=True,
        default='batch_issued',
        help=REQUEST_TYPE_DESCRIPTION,
    )
    receipt_type = fields.Selection(
        selection=list(RECEIPT_TYPE_SELECTION),
        default='I',
        help=RECEIPT_TYPE_DESCRIPTION,
    )
    cfdi_uuid = fields.Char()
    emission_date_from = fields.Date(
        compute="_compute_date_range",
        store=True, readonly=False,
    )
    emission_date_to = fields.Date(
        compute="_compute_date_range",
        store=True, readonly=False,
    )
    date_options = fields.Selection(
        [
            ('last_week', 'Last Week'),
            ('last_month', 'Last Month'),
        ],
        default="last_month",
    )

    @api.depends('date_options')
    def _compute_date_range(self):
        for wizard in self:
            # Using previous day in company's timezone.
            tz = wizard.company_id.partner_id.commercial_partner_id._l10n_mx_edi_get_cfdi_timezone()
            to_date = datetime.now(tz).date() - relativedelta(days=1)
            delta_kwarg = {'weeks': 1} if wizard.date_options == 'last_week' else {'months': 1}
            wizard.emission_date_to = to_date
            wizard.emission_date_from = to_date - relativedelta(**delta_kwarg)

    def action_create_cfdi_request(self):
        self.ensure_one()

        create_vals = {'company_id': self.company_id.id, 'request_type': self.request_type}

        if self.request_type == 'folio':
            create_vals['cfdi_uuid'] = self.cfdi_uuid
        else:
            create_vals.update({
                'emission_date_from': self.emission_date_from,
                'emission_date_to': self.emission_date_to,
                'receipt_type': self.receipt_type,
            })

        request = self.env['l10n_mx_edi.cfdi.request']._send_and_create_new_request(create_vals)

        if request.state == 'in_process_at_sat':
            notification_type = 'success'
            message = _('Request sent to SAT. Documents will arrive in the background.')
        else:
            notification_type = 'warning'
            message = request.message

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notification_type,
                'message': message,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
