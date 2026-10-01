from . import models
from . import controllers

from datetime import datetime, time, timedelta
from odoo import fields


def post_init(env):
    if env['res.groups']._is_feature_enabled('planning.group_field_service_allow_equipment'):
        if not env['res.groups']._is_feature_enabled('stock.group_production_lot'):
            env.ref('base.group_user')._apply_group(env.ref('stock.group_production_lot'))
        today = fields.Date.today()
        week_start = today - timedelta(days=today.weekday())
        # take into account the timezone
        week_start_safe = datetime.combine(week_start, time.min) - timedelta(hours=14)
        slots = env['planning.slot'].search([
            ('partner_id', '!=', False),
            ('lot_ids', '=', False),
            ('start_datetime', '>=', week_start_safe),
        ])
        if slots:
            slots._compute_lot_ids()
