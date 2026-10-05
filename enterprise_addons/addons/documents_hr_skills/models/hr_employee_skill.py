from odoo import api, models


class HrEmployeeSkill(models.Model):
    _inherit = 'hr.employee.skill'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.save_certificates()
        return records

    def write(self, vals):
        records = super().write(vals)
        if 'certificate_file' in vals:
            self.save_certificates()
        return records

    def save_certificates(self):
        self.env['documents.document'].create([{
            'raw': skill.certificate_file,
            'name': skill.certificate_file.filename,
            'folder_id': skill.employee_id.hr_employee_certificate_folder_id.id,
        } for skill in self if skill.certificate_file])
