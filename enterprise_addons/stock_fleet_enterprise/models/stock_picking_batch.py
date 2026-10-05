from datetime import timedelta

from odoo import _, api, fields, models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def action_picking_map_view(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock_fleet_enterprise.stock_picking_action_view_map')
        action['domain'] = [('id', 'in', self.picking_ids.ids)]
        return action

    def action_open_batch_from_gantt_view(self):
        """ Method to open the batch form view of the current record from the Gantt view.
        """
        self.ensure_one()
        view_id = self.env.ref('stock_fleet_enterprise.stock_picking_batch_view_form_plan_batch').id
        return {
            'name': _('Plan Batch'),
            'res_model': 'stock.picking.batch',
            'view_mode': 'form',
            'view_id': view_id,
            'type': 'ir.actions.act_window',
            'res_id': self.id,
            'target': 'new',
        }

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        gantt_data = super().get_gantt_data(domain, groupby, read_specification, limit=limit, offset=offset, unavailability_fields=unavailability_fields, progress_bar_fields=progress_bar_fields, start_date=start_date, stop_date=stop_date, scale=scale)

        if groupby == ['user_id'] or groupby == ['dock_id']:
            field = groupby[0]

            start_date = start_date or fields.Datetime.now()
            stop_date = stop_date or start_date + timedelta(days=7)
            limit_date = fields.Datetime.now() - timedelta(days=30)

            records = self.env['stock.picking.batch'].search_read([('scheduled_date', '>', limit_date), ('end_date', '<', stop_date), (field, '!=', False)], [field])
            groups_all = {record[field] for record in records}
            groups_now = {group[field] for group in gantt_data['groups']}
            groups_new = groups_all - groups_now
            gantt_data['groups'].extend([{field: group} for group in groups_new])

        return gantt_data
