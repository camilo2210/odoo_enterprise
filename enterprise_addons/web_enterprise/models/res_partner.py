from collections import defaultdict

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    contact_address_complete = fields.Char(compute='_compute_complete_address', store=True)

    @api.depends(lambda self: self._display_address_depends())
    def _compute_complete_address(self):
        for partner in self:
            partner.contact_address_complete = partner._display_address(without_name=True, separator=', ')

    @api.model
    def _address_fields(self):
        return super()._address_fields() + ['partner_latitude', 'partner_longitude']

    @api.model
    def _formatting_address_fields(self):
        """Returns the list of address fields usable to format addresses."""
        result = super()._formatting_address_fields()
        return [item for item in result if item not in ['partner_latitude', 'partner_longitude']]

    @api.model
    def update_latitude_longitude(self, partners):
        partners_data = defaultdict(list)

        for partner in partners:
            if 'id' in partner and 'partner_latitude' in partner and 'partner_longitude' in partner:
                partners_data[partner['partner_latitude'], partner['partner_longitude']].append(partner['id'])

        for coordinates, partner_ids in partners_data.items():
            partners = self.browse(partner_ids)
            if self.env.user.has_group('base.group_user'):
                partners = partners.sudo()
            # NOTE this should be done in sudo if internal user to avoid crashing as soon as the view is used
            partners.write({
                'partner_latitude': coordinates[0],
                'partner_longitude': coordinates[1],
            })

        return True
