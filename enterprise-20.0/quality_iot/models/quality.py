from odoo import fields, models


class QualityPoint(models.Model):
    _inherit = "quality.point"

    device_id = fields.Many2one(
        'iot.device',
        ondelete='restrict',
        domain=lambda self: [
            '&',
            '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id),
            ('type', 'in', ['device', 'scale', 'camera'])
        ],
        index='btree_not_null',
    )


class QualityCheck(models.Model):
    _inherit = "quality.check"

    identifier = fields.Char(related='point_id.device_id.identifier')
    iot_box_id = fields.Many2one(related='point_id.device_id.iot_id', store=False)
