from odoo import models


class HrEmployeeDeparture(models.Model):
    _inherit = "hr.employee.departure"

    def _get_departure_reason_domain(self):
        """
        For Uzbekistan companies, the departure reasons are very specific and some of the generic reasons do not make sense.
        If the currently selected company is in Uzbekistan, only show Uzbekistan specific reasons, else return the normal domain.
        """
        if self.env.company.country_id.code == 'UZ':
            return [('country_id.code', '=', 'UZ')]
        return super()._get_departure_reason_domain()
