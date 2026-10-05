# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def open_2306_and_2307(self):
        action = self.env["ir.actions.actions"]._for_xml_id("l10n_ph_reports.action_account_report_2306_and_2307")
        action['params'] = {
            'options': {
                'partner_ids': (self | self.commercial_partner_id).ids,
                'unfold_all': len(self.ids) == 1,
            },
            'ignore_session': True,
        }
        return action
