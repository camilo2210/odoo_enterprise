from dateutil.relativedelta import relativedelta

from odoo import api, models, fields


class AccountReturn(models.Model):
    _inherit = 'account.return'

    l10n_dk_validation_state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
        ],
        string="Status",
        default='pending',
        copy=False,
    )

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        # Extends account_reports
        if return_type_external_id == 'l10n_dk_reports.dk_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            periodicity = return_type._get_periodicity(company)
            if periodicity == 'trimester':
                return date_to + relativedelta(months=+3, day=1)
            elif periodicity == 'year':
                end_of_year = date_to + relativedelta(month=12, day=31)
                return end_of_year + relativedelta(months=+3, day=1)
            else:
                return date_to + relativedelta(days=25)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def _prepare_submission(self):
        # Extends account_reports
        if 'dk' in self.type_external_id:
            self.write({'l10n_dk_validation_state': 'pending'})
        if self.type_external_id == 'l10n_dk_reports.dk_ec_sales_list_return_type':
            return self.env['l10n_dk_reports.ec.sales.list.submission.wizard']._open_submission_wizard(self)

        if self.type_external_id == 'l10n_dk_reports.dk_tax_return_type':
            wizard = self.env['l10n_dk_reports.tax.report.calendar.wizard'].create({
                'return_id': self.id,
                'report_id': self.type_id.report_id.id,
                'company_id': self.env.company.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
            })
            return wizard._get_records_action(
                name=self.env._('Tax Report RSU Calendar'),
                target='new',
            )

        return super()._prepare_submission()

    def action_reset_tax_return_common(self):
        if 'dk' in self.type_external_id:
            self.write({'l10n_dk_validation_state': False})
        return super().action_reset_tax_return_common()

    def _compute_visible_states(self):
        # EXTENDS account_reports
        super()._compute_visible_states()
        for record in self:
            if 'dk' in record.type_external_id and record.state == 'submitted':
                alert_type = 'warning'
                msg = self.env._("Pending / Sent to Skat")
                if record.l10n_dk_validation_state == 'accepted':
                    alert_type = 'success'
                    msg = self.env._("Report accepted.")
                elif record.l10n_dk_validation_state == 'rejected':
                    alert_type = 'danger'
                    msg = self.env._("Report rejected. Please reset and fix.")
                new_visible_states = []
                for state_data in record.visible_states:
                    if state_data['name'] == 'submitted':
                        state_data['alert_type'] = alert_type
                        state_data['error_msg'] = msg
                    new_visible_states.append(state_data)
                record.visible_states = new_visible_states
