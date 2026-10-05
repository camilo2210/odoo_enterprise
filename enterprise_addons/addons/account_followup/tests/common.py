from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo import fields


class TestAccountFollowupCommon(AccountTestInvoicingCommon):
    _test_user_groups = None  # FIXME list needed groups

    def create_followup(self, delay, company_id=False):
        return self.env['account_followup.followup.line'].create({
            'delay': delay,
            'send_email': True,
            'company_id': company_id or self.company_data['company'].id
        })

    @classmethod
    def _create_invoice_followup(self, invoice_date, quantity=1.0, price_unit=500, partner=None, company_id=False, post=True):
        return self._create_invoice_one_line(
            quantity=quantity,
            price_unit=price_unit,
            date=invoice_date,
            invoice_date=invoice_date,
            invoice_date_due=invoice_date,
            partner_id=partner,
            company_id=company_id or self.company_data['company'].id,
            post=post,
        )

    def assertPartnerFollowup(self, partner, line, move=None):
        # Since we are querying multiple times with data changes in the same transaction (for the purpose of tests),
        # we need to invalidated the cache in database
        self.env.cr.cache.pop('res_partner_all_followup', None)
        res = partner._query_followup_data()
        if move:
            aml_id = res[partner.id]['aml_id']
            aml = self.env['account.move.line'].browse(aml_id)
            self.assertEqual(aml.move_id, move)
        self.assertEqual(res.get(partner.id, {}).get('followup_line_id'), line.id if line else None)

    def _execute_followup(self, partner, options={}):
        followup_data = partner._query_followup_data()
        followup_line_id = followup_data[partner.id]['followup_line_id']
        aml_id = followup_data[partner.id]['aml_id']
        followup_line = self.env['account_followup.followup.line'].browse(followup_line_id)
        aml = self.env['account.move.line'].browse(aml_id)
        options['followup_line'] = followup_line
        options['aml'] = aml
        partner._execute_followup_partner(options)

    def _get_followup_file_name(self):
        today = fields.Date.context_today(self).strftime('%m%d%Y')
        return f"{today}_Customer-Statement.pdf"
