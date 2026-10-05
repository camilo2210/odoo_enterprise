import uuid
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)

        if main_company.is_northern_irish():
            ec_sales_return_type = self.env.ref('l10n_uk_reports.uk_ec_sales_list_return_type')
            offset = ec_sales_return_type._get_periodicity_months_delay(main_company)
            date_in_previous_period = fields.Date.context_today(self) - relativedelta(months=offset)
            date_from, date_to = ec_sales_return_type._get_period_boundaries(main_company, date_in_previous_period)
            intracom_fpos = self.env.ref(f'account.{main_company.id}_account_fiscal_position_ni_to_eu_b2b', raise_if_not_found=False)

            if intracom_fpos:
                domain = [
                    ('tax_ids', 'in', intracom_fpos.tax_ids.ids),
                    ('balance', '!=', 0),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                    ('parent_state', '=', 'posted'),
                ]
                if self.env['account.move.line'].search_count(domain, limit=1):
                    ec_sales_return_type._try_create_return_for_period(date_from, main_company, tax_unit)

        return rslt


class AccountReturn(models.Model):
    _inherit = 'account.return'

    @api.model
    def _evaluate_deadline(self, company, return_type, return_type_external_id, date_from, date_to):
        if return_type_external_id == 'l10n_uk_reports.uk_tax_return_type' and not return_type.with_company(company).deadline_days_delay:
            return date_to + relativedelta(days=7) + relativedelta(months=1)

        return super()._evaluate_deadline(company, return_type, return_type_external_id, date_from, date_to)

    def action_submit(self):
        self.ensure_one()
        if self.type_external_id == 'l10n_uk_reports.uk_tax_return_type':
            return {
                'type': 'ir.actions.client',
                'tag': 'action_hmrc_add_client_data',
                'params': {
                    'active_id': self.id
                },
            }
        return super().action_submit()

    def action_open_send_to_hmrc_wizard(self, client_data=None):
        self.ensure_one()
        # Before opening the Send to HMRC wizard, we need to make sure the user has a valid vat token.
        if res := self.env['hmrc.service'].with_context(return_id=self.id)._login():
            return res

        context = self.env.context.copy()
        context.update({
            'return_id': self.id,
            'client_data': {
                **(client_data or {}),
                'hmrc_gov_client_device_id': uuid.uuid4()
            }
        })
        view_id = self.env.ref('l10n_uk_reports.hmrc_send_wizard_form').id
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Send to HMRC'),
            'res_model': 'l10n_uk.hmrc.send.wizard',
            'target': 'new',
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'context': context,
        }

    def l10n_uk_process_hmrc_vat_submission(self, client_data=None):
        self.ensure_one()
        # Block the user to select all the companies from the tax unit for consistent data filing.
        if self.tax_unit_id and not set(self.tax_unit_id.company_ids).issubset(self.env.companies):
            return {
                'type': 'ir.actions.client',
                'tag': 'l10n_uk_select_tax_unit',
                'params': {
                    'companies': self.tax_unit_id.company_ids.ids,
                }
            }

        # do the login if there is no token for the current user yet.
        if res := self.env['hmrc.service'].with_context(return_id=self.id)._login():
            return res

        return self.action_open_send_to_hmrc_wizard(client_data)
