from odoo import models
from odoo.tools import format_date


class HrExportWorkEntries(models.TransientModel):
    _inherit = 'hr.export.work.entries'

    def _get_columns(self, company):
        if company.country_code == 'BE':
            columns = [
                (self.env._('Date'), lambda args: format_date(self.env, args['date'])),
                (self.env._('Company'), lambda args: args['company'].name),
                (self.env._('Company External Code'), lambda args: args['company'].external_code or ''),
                (self.env._('Name'), lambda args: args['we_collection']['work_entries'][0]['work_entry_type_id']['name'] or ''),
                (self.env._('Code'), lambda args: args['we_collection']['work_entries'][0]['work_entry_type_id']['code'] or ''),
                (self.env._('External Code'), lambda args: args['we_collection']['work_entries'][0]['work_entry_type_id']['external_code'] or ''),
                (self.env._('Employee Name'), lambda args: args['employee_id'].name),
                (self.env._('Employee Ext. Code'), lambda args: args['employee_id'].external_code or ''),
                (self.env._('NISS'), lambda args: args['employee_id'].niss),
                (self.env._('Duration'), lambda args: str(round(int(args['we_collection']['duration'] // 3600), 2))),
            ]
            return columns
        else:
            return super()._get_columns(company)
