from .common import TestInterCompanyRulesCommonSOPO
from odoo.fields import Command
from odoo.tests import Form, tagged


@tagged('post_install', '-at_install')
class TestInterCompanyPurchaseToSale(TestInterCompanyRulesCommonSOPO):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.env['res.currency']._activate_group_multi_currency()

    def generate_purchase_order(self, company, partner):
        """ Generate purchase order and confirm its state """
        purchase_order = Form(self.env['purchase.order'])
        purchase_order.partner_id = partner
        purchase_order.company_id = company
        purchase_order = purchase_order.save()

        with Form(purchase_order) as po:
            with po.order_line.new() as line:
                line.name = 'Service'
                line.product_id = self.product_consultant
                line.price_unit = 450.0
                line.discount = 10.0

        # Confirm Purchase order
        purchase_order.button_confirm()
        # Check purchase order state should be purchase.
        self.assertEqual(purchase_order.state, 'purchase', 'Purchase order should be in purchase state.')
        return purchase_order

    def validate_generated_sale_order(self, purchase_order, company, partner):
        """ Validate sale order which has been generated from purchase order
        and test its state, total_amount, product_name and product_quantity.
        """

        # Find related sale order based on client order reference.
        sale_order = self.env['sale.order'].with_company(partner).search([('client_order_ref', '=', purchase_order.name)], limit=1)
        fp = self.env['account.fiscal.position'].with_company(partner)._get_fiscal_position(company.partner_id)

        self.assertEqual(sale_order.state, "draft", "sale order should be in draft state.")
        self.assertEqual(sale_order.partner_id, company.partner_id, "Vendor does not correspond to Company %s." % company)
        self.assertEqual(sale_order.company_id, partner, "Applied company in created sale order is incorrect.")
        self.assertEqual(sale_order.amount_total, 465.75, "Total amount is incorrect.")
        self.assertEqual(sale_order.order_line[0].product_id, self.product_consultant, "Product in line is incorrect.")
        self.assertEqual(sale_order.order_line[0].label, 'Service', "Product name is incorrect.")
        self.assertEqual(sale_order.order_line[0].product_uom_qty, 1, "Product qty is incorrect.")
        self.assertEqual(sale_order.order_line[0].price_unit, 450, "Unit Price in line is incorrect.")
        self.assertEqual(sale_order.order_line[0].price_subtotal, 405, "Subtotal in line is incorrect.")
        self.assertEqual(sale_order.fiscal_position_id, fp)


    def test_00_inter_company_sale_purchase(self):
        """ Configure "Sale/Purchase" option and then Create purchase order and find related
        sale order to related company and compare them.
        """

        # Generate purchase order in company A for company B
        self.company_b.update({
            'intercompany_generate_sales_orders': True,
            'intercompany_generate_purchase_orders': True,
        })
        purchase_order = self.generate_purchase_order(self.company_a, self.company_b.partner_id)
        # Check sale order is created in company B ( for company A )
        self.validate_generated_sale_order(purchase_order, self.company_a, self.company_b)
        # reset configuration of company B
        self.company_b.update({
            'intercompany_generate_sales_orders': False,
            'intercompany_generate_purchase_orders': False,
        })

        # Generate purchase order in company B for company A
        self.company_a.update({
            'intercompany_generate_sales_orders': True,
            'intercompany_generate_purchase_orders': True,
        })
        purchase_order = self.generate_purchase_order(self.company_b, self.company_a.partner_id)
        # Check sale order is created in company A ( for company B )
        self.validate_generated_sale_order(purchase_order, self.company_b, self.company_a)
        # reset configuration of company A
        self.company_a.update({
            'intercompany_generate_sales_orders': False,
            'intercompany_generate_purchase_orders': False,
        })

    def test_inter_company_sale_purchase_never_variant(self):
        """ Configure intercompany "Sale" option,
        Create a purchase order for a product with a never variant and compare to the related sale order in the other company.
        """

        self.company_b.update({
            'intercompany_generate_sales_orders': True,
            'intercompany_generate_purchase_orders': False,
        })
        no_variant_attr = self.env['product.attribute'].create({
            'name': "Attribute",
            'create_variant': 'no_variant',
            'value_ids': [
                Command.create({'name': "Value 1", 'sequence': 1}),
                Command.create({'name': "Value 2", 'sequence': 2}),
            ],
        })
        no_variant_product_tmpl = self.env['product.template'].create({
            'name': "No Variant",
            'attribute_line_ids': [Command.create({
                'attribute_id': no_variant_attr.id,
                'value_ids': no_variant_attr.value_ids.ids,
            })],
        })
        ptvi = no_variant_product_tmpl.attribute_line_ids.product_template_value_ids[0]
        purchase_order = self.env['purchase.order'].create({
            'partner_id': self.company_b.partner_id.id,
            'company_id': self.company_a.id,
            'order_line': [
                Command.create({
                    'product_id': no_variant_product_tmpl.product_variant_id.id,
                    'price_unit': 10.0,
                    'product_qty': 10,
                    'product_no_variant_attribute_value_ids': ptvi,
                }),
            ]
        })
        purchase_order.button_confirm()
        sale_order = self.env['sale.order'].with_company(self.company_b).search([('client_order_ref', '=', purchase_order.name)], limit=1)

        self.assertRecordValues(sale_order, [{
            "state": "draft",
            "partner_id": self.company_a.partner_id.id,
            "company_id": self.company_b.id,
            "amount_total": 115,
            }])
        self.assertRecordValues(sale_order.order_line[0], [{
            "product_id": no_variant_product_tmpl.product_variant_id.id,
            "label": 'No Variant\nAttribute: Value 1',
            "product_uom_qty": 10,
            "price_unit": 10,
            "price_subtotal": 100,
            "product_no_variant_attribute_value_ids": ptvi.ids
            }])

        self.company_b.update({
            'intercompany_generate_sales_orders': False,
            'intercompany_generate_purchase_orders': False,
        })

    def test_01_inter_company_purchase_order_with_configuration(self):
        """ Configure only "purchase" option and then Create purchase order and find related
        sale order to related company and compare them.
        """

        # Generate purchase order in company A for company B
        self.company_b.update({
            'intercompany_generate_sales_orders': True,
        })
        purchase_order = self.generate_purchase_order(self.company_a, self.company_b.partner_id)
        # Check sale order is created in company B ( for company A )
        self.validate_generated_sale_order(purchase_order, self.company_a, self.company_b)
        # reset configuration of company B
        self.company_b.update({
            'intercompany_generate_sales_orders': False,
        })

        # Generate purchase order in company B for company A
        self.company_a.update({
            'intercompany_generate_sales_orders': True,
        })
        purchase_order = self.generate_purchase_order(self.company_b, self.company_a.partner_id)
        # Check sale order is created in company A ( for company B )
        self.validate_generated_sale_order(purchase_order, self.company_b, self.company_a)
        # reset configuration  of company A
        self.company_a.update({
            'intercompany_generate_sales_orders': False,
        })

    def test_02_inter_company_purchase_order_without_configuration(self):
        """ Without any Configuration Create purchase order and try to find related
        sale order to related company.
        """

        # without any inter_company configuration generate purchase_order in company A for company B
        purchase_order = self.generate_purchase_order(self.company_a, self.company_b.partner_id)
        # Find related sale order based on client order reference.
        sale_order = self.env['sale.order'].search([('client_order_ref', '=', purchase_order.name)], limit=1)
        self.assertTrue((not sale_order), "Sale order created for company B from Purchase order of company A without configuration")

        # without any inter_company configuration generate purchase_order in company B for company A
        purchase_order = self.generate_purchase_order(self.company_b, self.company_a.partner_id)
        # Find related sale order based on client order reference.
        sale_order = self.env['sale.order'].search([('client_order_ref', '=', purchase_order.name)], limit=1)
        self.assertTrue((not sale_order), "Sale order created for company A from Purchase order of company B without configuration")

    def test_06_inter_company_purchase_order_from_so_with_sales_team(self):
        """
        Check that the default sales team used on the automatically generated SO
        belongs to the appropriate company.
        """
        # Automatically generate SO in COMP B if a PO is confirmed in COMP A for COMP B
        self.company_b.update({
             'intercompany_generate_sales_orders': True,
        })
        # Archive all the sales team and create a sales team for COMP A but not for COMP B
        self.env['crm.team'].search([]).action_archive()
        self.env['crm.team'].create({
            'name': 'Team A',
            'company_id': self.company_a.id,
        })
        # Generate purchase order in company A for company B
        purchase_order = self.generate_purchase_order(self.company_a, self.company_b.partner_id)
        # Check sale order is created in company B ( for company A )
        sale_order = self.env['sale.order'].with_company(self.company_b).search([('client_order_ref', '=', purchase_order.name)], limit=1)
        self.assertRecordValues(sale_order, [{
            'company_id': self.company_b.id,
            'team_id': False,
        }])
        # Create a sales Team for COMP B, proceed the same steps and check that it has been set as a default value
        valid_sales_team = self.env['crm.team'].create({
            'name': 'Team B',
            'company_id': self.company_b.id,
        })
        # Generate purchase order in company A for company B
        purchase_order_2 = self.generate_purchase_order(self.company_a, self.company_b.partner_id)
        # Check sale order is created in company B ( for company A )
        sale_order = self.env['sale.order'].with_company(self.company_b).search([('client_order_ref', '=', purchase_order_2.name)], limit=1)
        self.assertRecordValues(sale_order, [{
            'company_id': self.company_b.id,
            'team_id': valid_sales_team.id,
        }])
