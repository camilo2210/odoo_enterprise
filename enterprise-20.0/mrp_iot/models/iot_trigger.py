from odoo import models, fields


class IotTrigger(models.Model):
    _name = 'iot.trigger'
    _description = 'IoT Trigger'
    _order = 'sequence'

    sequence = fields.Integer(default=1)
    device_id = fields.Many2one('iot.device', 'Device', required=True, index=True, domain="[('type', '=', 'keyboard')]")
    key = fields.Char('Key')
    workcenter_id = fields.Many2one('mrp.workcenter', index='btree_not_null')
    action = fields.Selection([
        ('picture', 'Take Picture'),
        ('measure', 'Take Measure'),
        ('SKIP', 'Skip'),
        ('PAUS', 'Pause'),
        ('PREV', 'Previous'),
        ('NEXT', 'Next'),
        ('VALI', 'Validate'),
        ('CLMO', 'Close MO'),
        ('CLWO', 'Close WO'),
        ('FINI', 'Finish'),
        ('RECO', 'Record Production'),
        ('CANC', 'Cancel'),
        ('PROP', 'Print Operation'),
        ('PRSL', 'Print Delivery Slip'),
        ('PRNT', 'Print Labels'),
        ('PACK', 'Pack'),
        ('SCRA', 'Scrap'),
        ('pass', 'Pass'),
        ('fail', 'Fail'),
    ])
