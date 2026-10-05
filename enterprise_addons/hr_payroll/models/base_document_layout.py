from odoo import api, models
from odoo.exceptions import AccessError


class BaseDocumentLayout(models.TransientModel):
    _inherit = 'base.document.layout'

    def _is_payroll_layout_configurator(self):
        """ Checks if a payroll admin is the one opening the payslip layout wizard. """
        return self.env.user.has_group('hr_payroll.group_hr_payroll_manager') and self.env.context.get('payroll_document_layout_configurator')

    def _check_payroll_company_access(self, companies):
        """ Raises an error if one of the given companies is not one of the user's own. """
        allowed_company_ids = self.env.companies.ids
        if any(company.id not in allowed_company_ids for company in companies):
            raise AccessError(
                self.env._("You cannot configure the document layout for this company")
            )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """ Reads the company layout with sudo when a payroll admin fills the wizard. """
        payroll_wizards = self.filtered(lambda w: w._is_payroll_layout_configurator())

        super(BaseDocumentLayout, self - payroll_wizards)._onchange_company_id()

        if payroll_wizards:
            for wizard in payroll_wizards:
                wizard._check_payroll_company_access(wizard.company_id)

            # wizards sudoed for payroll admins to be able to read `external_report_layout_id` (an `ir.ui.view` type) on company
            super(BaseDocumentLayout, payroll_wizards.sudo())._onchange_company_id()

    def _get_asset_style(self):
        """ Builds the report styles with sudo when a payroll admin fills the wizard. """
        if not self._is_payroll_layout_configurator():
            return super()._get_asset_style()

        return self.env['ir.qweb']._render('web.styles_company_report', {
            'company_ids': self.sudo(),
        }, raise_if_not_found=False)
