from odoo import api, models


class AccountLockException(models.Model):
    _inherit = 'account.lock_exception'

    @api.model_create_multi
    def create(self, vals_list):
        exceptions = super().create(vals_list)

        if any(exception.lock_date_field in ('tax_lock_date', 'fiscalyear_lock_date') for exception in exceptions):
            self.env.ref('account_reports.ir_cron_garbage_collect_snapshots')._trigger()

        exceptions._create_report_snapshot_triggers_at_end_datetime()

        return exceptions

    def write(self, vals):
        if any(lock_date_field in vals.get('lock_date_field', {}) for lock_date_field in ('tax_lock_date', 'fiscalyear_lock_date')):
            self.env.ref('account_reports.ir_cron_garbage_collect_snapshots')._trigger()

        rslt = super().write(vals)

        if 'end_datetime' in vals:
            self._create_report_snapshot_triggers_at_end_datetime()

        return rslt

    def _create_report_snapshot_triggers_at_end_datetime(self):
        for end_datetime in set(self.filtered(lambda x: x.lock_date_field in ('tax_lock_date', 'fiscalyear_lock_date')).mapped('end_datetime')):
            if end_datetime:
                self.env.ref('account_reports.ir_cron_create_snapshots')._trigger(at=end_datetime)
