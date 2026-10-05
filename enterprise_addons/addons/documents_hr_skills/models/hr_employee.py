from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    hr_employee_certificate_folder_id = fields.Many2one('documents.document', string="HR Employee Certificate Folder", groups="base.group_system,hr.group_hr_user")

    def _generate_employee_documents_folders(self, skip_subfolders=False):
        super()._generate_employee_documents_folders(skip_subfolders=skip_subfolders)
        self._generate_employee_certificate_folder()

    def _generate_employee_certificate_folder(self):
        employees = self.filtered(lambda e: e.hr_employee_folder_id and not e.hr_employee_certificate_folder_id)
        if not employees:
            return
        folders = self.env["documents.document"].sudo().create([{
            'name': self.env._("Certificate"),
            'type': 'folder',
            'folder_id': employee.hr_employee_folder_id.id,
            'company_id': employee.company_id.id,
        } for employee in employees])
        for employee, folder in zip(employees, folders):
            employee.hr_employee_certificate_folder_id = folder

    def _get_reserved_employee_subfolders(self):
        return super()._get_reserved_employee_subfolders() | self.hr_employee_certificate_folder_id
