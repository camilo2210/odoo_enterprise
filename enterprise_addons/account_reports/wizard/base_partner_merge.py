from odoo import models


class BasePartnerMergeAutomaticWizard(models.TransientModel):
    _inherit = 'base.partner.merge.automatic.wizard'

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        rslt = super()._merge(partner_ids, dst_partner=dst_partner, extra_checks=extra_checks)

        # Merging partners rewrites partner_id on move lines at SQL level, without any lock date protection;
        # snapshots grouped by partner may contain stale results afterwards, and need to be regenerated.
        snapshots_to_unlink = self.env['account.report.snapshot'].sudo().search([('groupby', '=', 'partner_id')])
        if snapshots_to_unlink:
            snapshots_to_unlink.unlink()
            self.env.ref('account_reports.ir_cron_create_snapshots')._trigger()

        return rslt
