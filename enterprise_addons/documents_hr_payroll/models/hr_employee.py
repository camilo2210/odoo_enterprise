from odoo import fields, models
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    hr_employee_payroll_folder_id = fields.Many2one(
        'documents.document', string="HR Employee Payroll Folder",
        groups="base.group_system,hr_payroll.group_hr_payroll_user")

    def _get_linked_records(self):
        all_linked_records = super()._get_linked_records()
        for employee, employee_linked_records in all_linked_records.items():
            employee_linked_records['hr.payslip'] = employee.sudo().slip_ids.ids
        return all_linked_records

    def _generate_employee_documents_folders(self, skip_subfolders=False):
        """Add a Payroll subfolder for the employees."""
        super()._generate_employee_documents_folders(skip_subfolders=skip_subfolders)
        # Sudo to set payroll folder even if not-a-payroll-hr-user is creating the employee
        employees_without_payroll_folder_sudo = self.sudo().filtered(
            lambda e: e.hr_employee_folder_id and not e.hr_employee_payroll_folder_id)
        employees_without_payroll_folder_sudo.company_id._generate_missing_documents_hr_groups()
        payroll_folders_vals, payroll_access_vals, access_vals_list = [], [], []
        for employee_sudo in employees_without_payroll_folder_sudo:
            payroll_group = employee_sudo.company_id.documents_hr_payroll_group_id
            payroll_folders_vals.append({
                'name': self.env._("Payroll"),
                'type': 'folder',
                'folder_id': employee_sudo.hr_employee_folder_id.id,
                'company_id': employee_sudo.company_id.id,
                'access_internal': 'none',
                'access_via_link': 'none',
                'is_access_via_link_hidden': True,
                'owner_id': False,
                'access_ids': False,  # Prevent inheriting from parent
            })
            payroll_access_vals.append({'group_id': payroll_group.id, 'role': 'edit'} if payroll_group else False)

        payroll_folders_sudo = self.env["documents.document"].sudo().create(payroll_folders_vals)
        for employee_sudo, folder, access_vals in zip(employees_without_payroll_folder_sudo, payroll_folders_sudo, payroll_access_vals):
            employee_sudo.hr_employee_payroll_folder_id = folder.id
            if access_vals:
                access_vals_list.append(access_vals | {"document_id": folder.id})
        if access_vals_list:
            self.env["documents.access"].sudo().create(access_vals_list)

    def _get_reserved_employee_subfolders(self):
        return super()._get_reserved_employee_subfolders() | self.hr_employee_payroll_folder_id

    def action_resend_payslips(self):
        self.ensure_one()
        if not self.env.user.has_group('hr_payroll.group_hr_payroll_user'):
            raise UserError(self.env._('You can not send the documents link to the employee.'))

        valid_payslips = self.slip_ids.filtered(lambda ps: ps.state in ['done', 'paid'] and ps.document_access_url)
        if not valid_payslips:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': self.env._("Resend All Employee's Payslips"),
                    'type': 'warning',
                    'message': self.env._('There is no valid payslip to send to the employee.')
                }
            }
        return {
            'name': self.env._('Send Email'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'view_mode': 'form',
            'res_model': 'hr.payslip.send.mail',
            'context': {
                'default_payslip_ids': valid_payslips.ids,
            },
        }
