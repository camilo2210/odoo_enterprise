# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestMergeProductTemplate(TransactionCase):

    def setUp(self):
        super().setUp()

        self.product1 = self.env['product.template'].create({'name': 'Test Product'})
        self.product2 = self.env['product.template'].create({'name': 'Test Product'})

        self.DMModel = self.env['data_merge.model'].create({
            'name': 'product template merge',
            'res_model_id': self.env['ir.model']._get('product.template').id,
            'domain': [('id', 'in', [self.product1.id, self.product2.id])],
        })

        self.env['data_merge.rule'].create({
            'model_id': self.DMModel.id,
            'field_id': self.env['ir.model.fields']._get('product.template', 'name').id,
            'match_mode': 'exact',
        })

    def test_merge_failure_multiple_variants(self):
        """Test that merging is blocked when a template has multiple variants due to attributes and raises a UserError."""
        attribute = self.env['product.attribute'].create({'name': 'Size'})
        value1 = self.env['product.attribute.value'].create({'name': 'S', 'attribute_id': attribute.id})
        value2 = self.env['product.attribute.value'].create({'name': 'M', 'attribute_id': attribute.id})

        self.env['product.template.attribute.line'].create({
            'product_tmpl_id': self.product1.id,
            'attribute_id': attribute.id,
            'value_ids': [Command.set([value1.id, value2.id])]
        })

        self.DMModel.find_duplicates()

        groups = self.env['data_merge.group'].search([('model_id', '=', self.DMModel.id)])
        self.assertEqual(len(groups), 1)

        with self.assertRaises(UserError):
            groups.merge_records()

    def test_merge_success_single_variant(self):
        """Test that merging two single variant templates completes successfully with the source variant archived."""
        self.DMModel.find_duplicates()

        groups = self.env['data_merge.group'].search([('model_id', '=', self.DMModel.id)])
        self.assertEqual(len(groups), 1)

        # Make product1 the master record before merging to avoid a product creation mismatch during the merge.
        groups.record_ids.write({'is_master': False})
        groups.record_ids.filtered(lambda r: r.res_id == self.product1.id).is_master = True
        groups.merge_records()

        self.assertFalse(self.env['product.template'].browse(self.product2.id).active)
        self.assertTrue(self.env['product.template'].browse(self.product1.id).active)
