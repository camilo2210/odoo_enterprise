from odoo import fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain


class AccountReturn(models.Model):
    _inherit = 'account.return'

    l10n_ro_fax = fields.Char(
        string="Fax",
        help="Fax number of the organization.",
    )
    l10n_ro_d390_corrective_declaration = fields.Boolean(
        string="Corrective declaration",
        help="Is this return corrected/rectified?",
    )

    ####################################################################################################
    ####  State Actions
    ####################################################################################################

    def action_validate(self):
        # OVERRIDE
        if self.type_external_id == 'l10n_ro_reports_d390.ro_ec_sales_list_return_type':
            ro_tax_tags = self.env['l10n_ro.ec.sales.report.handler']._get_ec_sales_tax_tags()
            ec_sales_tag_ids = {tax_tag for sale_type in ro_tax_tags.values() for tax_tag in sale_type}
            aml = self.env['account.move.line'].search(
                domain=Domain([
                    ('tax_tag_ids', 'in', ec_sales_tag_ids),
                    ('company_id', 'in', self.company_ids.ids),
                    ('date', '>=', self.date_from),
                    ('date', '<=', self.date_to),
                    ('parent_state', '=', 'posted'),
                ]),
                limit=1,
            )
            if not aml:
                raise UserError(self.env._("No operations to report in the current period."))

            new_wizard = self.env['l10n_ro_reports_d390.generate.ec.sales.report.wizard'].create({'return_id': self.id})
            return {
                'type': 'ir.actions.act_window',
                'name': self.env._('Declaration information'),
                'view_mode': 'form',
                'res_model': 'l10n_ro_reports_d390.generate.ec.sales.report.wizard',
                'target': 'new',
                'res_id': new_wizard.id,
                'views': [(self.env.ref('l10n_ro_reports_d390.generate_ec_sales_report_wizard_form').id, 'form')],
                'context': {
                    'dialog_size': 'medium',
                },
            }

        return super().action_validate()

    def action_submit(self):
        # OVERRIDE
        if self.type_external_id == 'l10n_ro_reports_d390.ro_ec_sales_list_return_type':
            return self.env['l10n_ro_reports_d390.ec.sales.list.submission.wizard']._open_submission_wizard(self)

        return super().action_submit()
