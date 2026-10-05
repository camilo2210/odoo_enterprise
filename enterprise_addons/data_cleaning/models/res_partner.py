# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

import datetime


class ResPartner(models.Model):
    _inherit = 'res.partner'
    # As this model has his own data merge, avoid to enable the generic data_merge on that model.
    _disable_data_merge = True

    def _merge_method(self, destination, source):
        """ The base partner merge wizard has a limit of 3 partners maximum.
        We process 2 source partners per cron call (2 source + 1 destination = 3 total).
        The remaining partners will be processed in subsequent cron runs.
        """
        # Prevent merging partners that are linked to already hashed journal items. (account)
        if 'account.move.line' in self.env and self.env['account.move.line'].sudo().search_count([('move_id.inalterable_hash', '!=', False), ('partner_id', 'in', source.ids)], limit=1):
            return {
                'error': self.env._('Partners that are used in hashed entries cannot be merged.')
            }

        source = source if source else self.env['res.partner']
        source_list = list(source)[:2]

        if source_list:
            wizard = self.env['base.partner.merge.automatic.wizard'].with_context({
                'active_ids': [destination.id] + [p.id for p in source_list],
                'active_model': 'res.partner'
            }).create({'dst_partner_id': destination.id})
            wizard.action_merge()

        return {
            'records_merged': len(source_list) + 1,
            'log_chatter': True,
            'post_merge': False,
        }

    def _elect_method(self, records):
        return records.sorted(
            key=lambda p: (not p.active, (p.create_date or datetime.datetime(1970, 1, 1))),
        )[:1]

    def _get_merge_result_values(self, destination, source):
        """Return final values after merging source into destination.
        This method uses the standard partner merge wizard to compute the values
        that would be written to the destination record.

        Since `_merge_values` returns technical field names as keys, they are
        converted to field labels for better readability in the merge preview.

        :param destination: record of master `res.partner`.
        :param source: record of source `res.partner`.
        :return: Dict of field labels and values that would be merged to the destination after merge.
        """
        merge_values = self.env['base.partner.merge.automatic.wizard']._merge_values(source, destination)["values"]

        # Convert technical field names to field descriptions.
        return {
            destination._fields[field].string: value
            for field, value in merge_values.items()
            if field in destination._fields
        }
