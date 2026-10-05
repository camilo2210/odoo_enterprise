# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductAvataxCategory(models.Model):
    _name = 'product.avatax.category'
    _description = "Avatax Product Category"
    _rec_name = 'code'
    _rec_names_search = ('description', 'code')

    code = fields.Char(required=True)
    description = fields.Char(required=True)

    @api.depends('code', 'description')
    def _compute_display_name(self):
        for category in self:
            category.display_name = _('[%(code)s] %(description)s', code=category.code, description=(category.description or '')[:50])


class ProductCategory(models.Model):
    _inherit = 'product.category'

    avatax_category_id = fields.Many2one(
        'product.avatax.category',
        help="https://taxcode.avatax.avalara.com/",
    )

    def _get_avatax_category_id(self):
        categ = self
        while categ and not categ.avatax_category_id:
            categ = categ.parent_id
        return categ.avatax_category_id


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    avatax_category_id = fields.Many2one(
        'product.avatax.category',
        help="https://taxcode.avatax.avalara.com/",
    )
    avatax_parameter_value_ids = fields.One2many(
        'avatax.parameter.value',
        string='Avatax Parameters',
        compute='_compute_avatax_parameter_value_ids',
        inverse='_inverse_avatax_parameter_value_ids',
        help='Per-product attributes sent to Avalara to refine tax calculation. Leave empty to let Avalara tax this product using only its category.',
    )

    def _get_avatax_category_id(self):
        return self.avatax_category_id or self.categ_id._get_avatax_category_id()

    @api.depends('product_variant_ids.avatax_parameter_value_ids')
    def _compute_avatax_parameter_value_ids(self):
        self._compute_template_field_from_variant_field('avatax_parameter_value_ids')

    def _inverse_avatax_parameter_value_ids(self):
        self._set_product_variant_field('avatax_parameter_value_ids')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    avatax_category_id = fields.Many2one(
        'product.avatax.category',
        help="https://taxcode.avatax.avalara.com/",
    )
    avatax_parameter_value_ids = fields.One2many(
        'avatax.parameter.value',
        'product_id',
        help='Per-product attributes sent to Avalara to refine tax calculation. Leave empty to let Avalara tax this product using only its category.',
    )

    def _get_avatax_category_id(self):
        return self.avatax_category_id or self.product_tmpl_id._get_avatax_category_id()
