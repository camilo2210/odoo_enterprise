# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    version = fields.Integer('Version', aggregator=False, default=1, copy=False, help="The current version of the product.")
    eco_count = fields.Integer('# ECOs',compute='_compute_eco_count')
    eco_ids = fields.One2many('mrp.eco', 'product_tmpl_id', 'ECOs')
    version_count = fields.Integer('# Versions', compute='_compute_version_count')

    def _compute_eco_count(self):
        eco_count_map = dict(self.env['mrp.eco']._read_group(
            [('product_tmpl_id', 'in', self.ids)],
            ['product_tmpl_id'], ['__count']
        ))
        for product in self:
            product.eco_count = eco_count_map.get(product, 0)

    def _compute_version_count(self):
        for product in self:
            product.version_count = len(product._get_version_products())

    def _get_version_products(self):
        self.ensure_one()
        bom_model = self.env['mrp.bom'].with_context(active_test=False)
        product_ids = set(self.ids)
        boms_to_check_ids = set(bom_model.search([
            ('product_tmpl_id', 'in', product_ids),
        ]).ids)
        checked_bom_ids = set()

        # Walk the BoM revision graph until no new version link is found.
        while boms_to_check_ids:
            checked_bom_ids.update(boms_to_check_ids)
            boms_to_check = bom_model.browse(boms_to_check_ids)

            # Follow the BoM revisions in both directions.
            related_boms = bom_model.search([
                '|',
                ('previous_bom_id', 'in', boms_to_check_ids),
                ('id', 'in', boms_to_check.previous_bom_id.ids),
            ])
            bom_product_ids = set(related_boms.product_tmpl_id.ids)

            # Add newly discovered products and queue their BoMs for the next pass.
            product_ids.update(bom_product_ids)
            boms_to_check_ids = set(related_boms.ids)
            boms_to_check_ids.update(bom_model.search([
                ('product_tmpl_id', 'in', bom_product_ids),
            ]).ids)
            boms_to_check_ids.difference_update(checked_bom_ids)
        return self.browse(product_ids)

    def mrp_eco_action_product_tmpl(self):
        action = self.env["ir.actions.actions"]._for_xml_id("mrp_plm.mrp_eco_action_product_tmpl")
        action['context'] = {'default_product_tmpl_id': self.id}
        action['domain'] = [('product_tmpl_id', '=', self.id)]
        return action

    def action_open_product_versions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('product.product_template_action_all')
        action['name'] = _('Versions')
        action['domain'] = [('id', 'in', self._get_version_products().ids)]
        action['context'] = {}
        action['view_mode'] = 'list,form'
        action['views'] = [(False, 'list'), (False, 'form')]
        return action
