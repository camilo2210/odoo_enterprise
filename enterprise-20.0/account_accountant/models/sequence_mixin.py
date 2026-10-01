from datetime import date, datetime
from odoo import models


class SequenceMixin(models.AbstractModel):
    _inherit = 'sequence.mixin'

    def _validate_fiscalyear_difference(self, start_year, end_year):
        """ Checks if there exists a fiscal year corresponding to the start and end date """
        formatted_start_year = datetime.strptime(start_year, "%y").year if len(start_year) == 2 else int(start_year)
        formatted_start_end = datetime.strptime(end_year, "%y").year if len(end_year) == 2 else int(end_year)

        computed_fiscalyear = self.env.company.compute_fiscalyear_dates(date(formatted_start_year, 12, 31))
        return computed_fiscalyear['date_from'].year == formatted_start_year and computed_fiscalyear['date_to'].year == formatted_start_end
