from odoo import models, fields

# Used for printing a field service report


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    l10n_din5008_date = fields.Date(default=fields.Date.context_today, store=False)
