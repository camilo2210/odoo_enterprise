from odoo import fields, models
from odoo.fields import Domain


class ResPartner(models.Model):
    _inherit = 'res.partner'

    scheduled_datetime = fields.Datetime('Scheduled Date', compute='_compute_scheduled_datetime', groups='planning.group_planning_user', export_string_translation=False)

    def _compute_scheduled_datetime(self):
        domain = Domain([
            ('sale_line_id', '!=', False),
            ('start_datetime', '!=', False),
        ])
        all_partners_and_children = {}
        all_partner_ids = set()
        for partner in self:
            all_partners_and_children[partner] = partner._get_child_partners().ids
            all_partner_ids.update(all_partners_and_children[partner])
        # partner_id is stored when field service feature is installed
        groupby = ['partner_id' if self.env['planning.slot']._fields['partner_id'].store else 'sale_order_id.partner_id']
        future_scheduled_datetimes = dict(self.env['planning.slot']._read_group(
            domain & Domain([
                ('end_datetime', '>=', fields.Datetime.now()),
                ('partner_id', 'in', all_partner_ids),
            ]),
            groupby,
            ['start_datetime:min'],
        ))
        remaining_partners = self.env['res.partner'].browse(all_partner_ids).filtered(lambda r: r not in future_scheduled_datetimes)
        past_scheduled_datetimes = {}
        if remaining_partners:
            past_scheduled_datetimes = dict(self.env['planning.slot']._read_group(
                domain & Domain([
                    ('end_datetime', '<', fields.Datetime.now()),
                    ('partner_id', 'in', remaining_partners.ids),
                ]),
                groupby,
                ['start_datetime:max'],
            ))
        for partner, child_ids in all_partners_and_children.items():
            future_date = min((date for partner, date in future_scheduled_datetimes.items() if partner.id in child_ids), default=False)
            if future_date:
                partner.scheduled_datetime = future_date
            else:
                past_date = max((date for partner, date in past_scheduled_datetimes.items() if partner.id in child_ids), default=False)
                partner.scheduled_datetime = past_date

    def _get_child_partners(self):
        return self.search([('id', 'child_of', self.ids)])

    def _get_last_planning_sale_line(self):
        return self.env['sale.order.line'].search([
            ('product_id.planning_enabled', '=', True),
            ('order_partner_id', 'in', self._get_child_partners().ids),
        ], order='create_date desc', limit=1)

    def action_open_planning_slots(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("planning.planning_action_schedule_by_resource")
        initial_date = self.scheduled_datetime or fields.Date.context_today(self)
        action.update({
            'domain': [
                ('sale_line_id', '!=', False),
                ('partner_id', 'in', self._get_child_partners().ids)
            ],
            'context': {
                'default_partner_id': self.id,
                'default_sale_line_id': self._get_last_planning_sale_line().id,
                'initialDate': initial_date,
            }
        })
        return action
