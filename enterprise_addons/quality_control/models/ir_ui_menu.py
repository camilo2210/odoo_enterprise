from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible_ids = super()._visible_menu_ids(debug)
        if not self.env.user.has_group('base.group_user_regular'):
            quality_root = self.env['ir.model.data']._xmlid_to_res_id('quality_control.menu_quality_root', raise_if_not_found=False)
            return visible_ids - {quality_root}
        return visible_ids
