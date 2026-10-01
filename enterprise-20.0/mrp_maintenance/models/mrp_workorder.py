# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    def button_maintenance_req(self):
        self.ensure_one()
        return {
            'name': _('New Maintenance Request'),
            'view_mode': 'form',
            'views': [(False, 'form')],
            'res_model': 'maintenance.request',
            'type': 'ir.actions.act_window',
            'context': {
                'default_company_id': self.company_id.id,
                'default_workorder_id': self.id,
                'default_production_id': self.production_id.id,
                'discard_on_footer_button': True,
            },
            'target': 'new',
            'domain': [('workorder_id', '=', self.id)]
        }

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        if field != 'workcenter_id':
            return super()._gantt_unavailability(field, res_ids, start, stop, scale)
        return self.env['mrp.workcenter']._get_gantt_unavailability(res_ids, start, stop, from_model=self._name)
