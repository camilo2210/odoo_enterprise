# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class L10nBeEmployeeDepartureHolidayAttestLine(models.Model):
    _name = 'l10n.be.employee.departure.holiday.attest.line'
    _description = 'Holiday Attest Time Off Line'

    departure_id = fields.Many2one('hr.employee.departure', index='btree_not_null')
    year = fields.Integer()
    work_entry_type_id = fields.Many2one('hr.work.entry.type', string='Time Type',
        domain="[('id', 'in', allowed_work_entry_type_ids)]")
    allowed_work_entry_type_ids = fields.Many2many(
        'hr.work.entry.type', compute='_compute_allowed_work_entry_type_ids')
    leave_allocation_count = fields.Float(string='Allocations')
    leave_allocation_count_show = fields.Char(compute='_compute_holiday_attest_lines_show')
    leave_count = fields.Float(string="Leaves")
    leave_count_show = fields.Char(compute='_compute_holiday_attest_lines_show')
    left_leave_count_show = fields.Char(compute='_compute_holiday_attest_lines_show')
    work_entry_type_and_year = fields.Char(compute='_compute_work_entry_type_and_year')

    @api.depends('leave_allocation_count', 'leave_count')
    def _compute_holiday_attest_lines_show(self):
        for line in self:
            line.leave_allocation_count_show = self.env._("%(count)s Allocated", count=line.leave_allocation_count)
            line.leave_count_show = self.env._("%(count)s Taken", count=line.leave_count)
            line.left_leave_count_show = self.env._("%(count)s Left", count=line.leave_allocation_count - line.leave_count)

    @api.depends('year', 'departure_id.departure_date', 'work_entry_type_id')
    def _compute_work_entry_type_and_year(self):
        for line in self:
            year_n = line.departure_id.departure_date.year if line.departure_id.departure_date else fields.Date.today().year
            delta = year_n - line.year
            suffix = {0: 'N', 1: 'N-1', 2: 'N-2'}.get(delta)
            line.work_entry_type_and_year = f"{line.work_entry_type_id.display_name} ({suffix})" if suffix \
                else f"{line.work_entry_type_id.display_name} (older)"

    @api.depends_context('company')
    def _compute_allowed_work_entry_type_ids(self):
        for attest_line in self:
            country = self.env.company.country_id
            if not country or not self.env['hr.work.entry.type'].search_count([('country_id', '=', country.id)], limit=1):
                domain = [('country_id', '=', False)]
            else:
                domain = [('country_id', '=', country.id)]
            attest_line.allowed_work_entry_type_ids = self.env['hr.work.entry.type'].search(domain)
