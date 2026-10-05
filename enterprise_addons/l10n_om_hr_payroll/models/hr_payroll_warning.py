from odoo import models


class HrPayrollWarning(models.Model):
    _inherit = 'hr.payroll.warning'

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "Employee":
            return self.env._("Employee")
        if text == "Kindly configure the company's MOL registration number":
            return self.env._("Kindly configure the company's MOL registration number")
        if text == "Kindly configure the Salary Payer":
            return self.env._("Kindly configure the Salary Payer")
        if text == "Kindly configure the Salary Payer's MOL registration number":
            return self.env._("Kindly configure the Salary Payer's MOL registration number")
        if text == "Kindly configure the WPS Disbursement Bank Account for the Salary Payer":
            return self.env._("Kindly configure the WPS Disbursement Bank Account for the Salary Payer")
        if text == "Missing identification number for the employee: %(label)s":
            return self.env._("Missing identification number for the employee: %(label)s", **kwargs)
        if text == "Payroll Structure":
            return self.env._("Payroll Structure")
        if text == "Salary frequency %(frequency)s is not supported by the Oman WPS format. Only Monthly and Bi-weekly are allowed.":
            return self.env._("Salary frequency %(frequency)s is not supported by the Oman WPS format. Only Monthly and Bi-weekly are allowed.", **kwargs)
        if text == "Settings":
            return self.env._("Settings")
        if text == "The WPS Disbursement Bank Account does not belong to the configured Salary Payer":
            return self.env._("The WPS Disbursement Bank Account does not belong to the configured Salary Payer")
        if text == "The WPS Disbursement Bank Account has no WPS Short Name or no BIC, the bank code for the WPS export cannot be determined":
            return self.env._("The WPS Disbursement Bank Account has no WPS Short Name or no BIC, the bank code for the WPS export cannot be determined")
        return super()._get_payroll_translation(text, **kwargs)
