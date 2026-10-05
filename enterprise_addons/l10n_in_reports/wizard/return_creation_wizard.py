from odoo import models


class AccountReturnCreationWizard(models.TransientModel):
    _name = "account.return.creation.wizard"
    _inherit = "account.return.creation.wizard"

    def _compute_is_create_disabled(self):
        super()._compute_is_create_disabled()
        iff_return_type = self.env.ref('l10n_in_reports.in_gstr_iff_return_type', raise_if_not_found=False)
        if not iff_return_type:
            return
        for wizard in self:
            if (
                wizard.return_type_id == iff_return_type
                and wizard.company_id.country_id.code == 'IN'
                and wizard.company_id.account_return_periodicity == 'trimester'
                and wizard.date_to.month in (3, 6, 9, 12)
            ):
                wizard.is_create_disabled = True
