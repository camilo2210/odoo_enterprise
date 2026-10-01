# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools import convert


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _load_restaurant_demo_data(self, with_demo_data=True):
        super()._load_restaurant_demo_data(with_demo_data)

        if with_demo_data:
            convert.convert_file(self._env_with_clean_context(), 'pos_restaurant_appointment', 'demo/pos_restaurant_appointment_demo.xml',
                idref=None,
                mode='init',
                noupdate=True,
            )
