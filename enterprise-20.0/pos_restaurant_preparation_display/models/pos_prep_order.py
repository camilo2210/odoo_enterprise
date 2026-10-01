from odoo import models, fields, api, _


class PosPrepOrder(models.Model):
    _inherit = 'pos.prep.order'

    pos_course_id = fields.Many2one('restaurant.order.course')

    @api.model
    def fire_course(self, order_id, course_id):
        order = self.env['pos.order'].browse(order_id)
        course = self.env['restaurant.order.course'].browse(course_id)
        course.write({
            "fired": True,
        })
        for display in course.line_ids.prep_line_ids.prep_display_ids:
            display._send_load_orders_message(True, _("%s Fired", course.name), order.id)


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.model
    def _load_pos_preparation_data_fields(self):
        res = super()._load_pos_preparation_data_fields()
        return res + ['course_id', 'uuid']
