from odoo import api, models, modules


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _get_activity_groups(self):
        activities = super()._get_activity_groups()
        activity_names = {
            'account.return': self.env._("Tax Returns"),
            'account.return.check': self.env._("Tax Return Checks"),
        }

        for activity in activities:
            if name := activity_names.get(activity['model']):
                activity |= {
                    'name': name,
                    'icon': modules.module.get_module_icon('accountant'),
                    'view_type': 'kanban',
                }

        return activities
