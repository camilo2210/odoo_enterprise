# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    documents_hr_payroll_group_id = fields.Many2one(
        'res.group.functional', string="Payroll Documents Default Group",
        help="Group given editor access on the Employees and Payroll folders created from now on. "
             "Changing it does not affect the existing folders.")

    def _get_documents_employee_folders_editor_groups(self):
        return super()._get_documents_employee_folders_editor_groups() | self.documents_hr_payroll_group_id

    def _generate_missing_documents_hr_groups(self):
        super()._generate_missing_documents_hr_groups()
        for company in self.filtered(lambda c: c.active and not c.documents_hr_payroll_group_id):
            company.sudo().documents_hr_payroll_group_id = self.env["res.group.functional"].sudo().create({
                'name': self.env._("Payroll (%(company_name)s)", company_name=company.name),
                'responsible_ids': [Command.link(company._get_documents_hr_group_responsible().id)],
                'user_ids': [Command.set(company._get_documents_hr_payroll_group_users().ids)],
            })

    def _get_documents_hr_payroll_group_users(self):
        """ Users added as members of the payroll documents group of the company. """
        self.ensure_one()
        return self._get_company_group_users(self.env.ref("hr_payroll.group_hr_payroll_user"))
