from odoo import Command
from odoo.tests import Form, tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestBillsPrediction(AccountTestInvoicingCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def get_default_groups(cls):
        groups = super().get_default_groups()
        return groups + cls.env.ref('analytic.group_analytic_accounting')

    def test_po_prediction(self):
        project_plan, _other_plans = self.env['account.analytic.plan']._get_all_plans()
        analytic_a = self.env['account.analytic.account'].create({'name': 'a', 'plan_id': project_plan.id})
        analytic_b = self.env['account.analytic.account'].create({'name': 'b', 'plan_id': project_plan.id})
        analytic_c = self.env['account.analytic.account'].create({'name': 'c', 'plan_id': project_plan.id})

        previous_bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            "partner_id": self.partner_a.id,
            "invoice_date": '2017-01-01',
            "invoice_line_ids": [
                Command.create({
                    'product_id': self.product_a.id,
                    'name': self.product_a.name,
                    'tax_ids': False,
                    'analytic_distribution': {str(analytic_a.id): 100},
                }),
            ],
        })
        previous_bill.action_post()

        po = self.env['purchase.order'].create({
            "partner_id": self.partner_a.id,
            "order_line": [Command.create({
                'product_id': self.product_a.id,
                'name': self.product_a.name,
                'tax_ids': False,
                'analytic_distribution': {str(analytic_b.id): 100},
            })],
        })
        po.button_confirm()

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            "partner_id": self.partner_a.id,
            "invoice_date": '2017-01-01',
            "invoice_line_ids": [
                Command.create({
                    'purchase_line_id': po.order_line.id,
                    'product_id': self.product_a.id,
                    'name': 'something else',
                    'tax_ids': False,
                    'analytic_distribution': {str(analytic_b.id): 100},
                }),
                Command.create({
                    'product_id': self.product_a.id,
                    'name': 'something different',
                    'tax_ids': False,
                    'analytic_distribution': {str(analytic_c.id): 100},
                }),
            ],
        })

        with Form(bill) as bill_form:
            with bill_form.invoice_line_ids.edit(0) as line_form:
                line_form.name = self.product_a.name
            with bill_form.invoice_line_ids.edit(1) as line_form:
                line_form.name = self.product_a.name
        bill = bill_form.save()

        self.assertRecordValues(bill.invoice_line_ids, [
            {'analytic_distribution': {str(analytic_b.id): 100}},  # not changed because value comes from PO
            {'analytic_distribution': {str(analytic_a.id): 100}},  # changed because value does not come from PO
        ])
