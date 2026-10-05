# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase
from odoo.tests import tagged, Form


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestQualityCheck(TransactionCase):

    def test_change_quality_point(self):
        """
        Test that a quality point can be used with an incompatible product and that a change of
        a quality piont changes the test_type of the quality check accordingly.
        """
        product_a = self.env['product.product'].create({
            'name': 'product a',
        })
        product_b = self.env['product.product'].create({
            'name': 'product b',
        })
        qp_product_a = self.env['quality.point'].create({
            'product_ids': [(4, product_a.id)],
            'test_type_id': self.env.ref('quality.test_type_instructions').id,
        })
        qp_product_b = self.env['quality.point'].create({
            'product_ids': [(4, product_b.id)],
            'test_type_id': self.env.ref('quality.test_type_picture').id,
        })
        qc = self.env['quality.check'].create({
                'product_id': product_b.id,
                'point_id': qp_product_b.id,
                'team_id': self.env['quality.check'].team_id.search([], limit=1).id,
            })
        qc_form = Form(qc)
        self.assertEqual(qc.test_type_id, qp_product_b.test_type_id)
        qc_form.point_id = qp_product_a
        qc = qc_form.save()
        self.assertEqual(qc.product_id, product_b)
        self.assertEqual(qc.test_type_id, qp_product_a.test_type_id)
        self.assertEqual(qc.point_id, qp_product_a)

    def test_duplicates_quality_checks(self):
        """
        Test that the quality.check model's name and control_date fields are not copied when duplicating a quality.check
        """
        qc_a = self.env['quality.check'].create({
            'team_id': self.env['quality.check'].team_id.search([], limit=1).id,
            'test_type_id': self.env['quality.check'].test_type_id.search([], limit=1).id,
        })
        next_name = self.env['ir.sequence'].search([('code', '=', 'quality.check')]).number_next_actual
        qc_a.do_pass()
        qc_b = qc_a.copy()

        self.assertNotEqual(qc_a.name, qc_b.name)
        self.assertEqual(qc_b.name, f"QC{next_name:05d}")

        self.assertTrue(qc_a.control_date)
        self.assertFalse(qc_b.control_date)
