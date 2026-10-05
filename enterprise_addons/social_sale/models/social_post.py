# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields
from odoo.tools import SQL


class SocialPost(models.Model):
    _inherit = 'social.post'

    sale_quotation_count = fields.Integer('Quotation Count', groups='sales_team.group_sale_salesman',
                                          compute='_compute_sale_quotation_count', compute_sudo=True)
    sale_invoiced_amount = fields.Monetary('Invoiced Amount', groups='sales_team.group_sale_salesman',
                                           compute='_compute_sale_invoiced_amount', compute_sudo=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', compute='_compute_currency_id', compute_sql="_compute_sql_currency_id", compute_sudo=True, string='Currency')

    @api.depends_context('company')
    def _compute_currency_id(self):
        self.currency_id = self.env.company.currency_id

    def _compute_sql_currency_id(self, table):
        return SQL("%s", self.env.company.currency_id.id)

    def _compute_sale_quotation_count(self):
        quotation_data = dict(
            self.env['sale.order']._read_group(
                [('utm_reference', 'in', [f'{post._name},{post.id}' for post in self])],
                ['utm_reference'], ['__count'])
            )
        for post in self:
            post.sale_quotation_count = quotation_data.get(f'{post._name},{post.id}', 0)

    def _compute_sale_invoiced_amount(self):
        if self:
            query = """SELECT move.utm_reference as utm_reference, SUM(line.price_total / COALESCE(currency_rate.rate, 1)) as price_total_converted_sum
                        FROM account_move_line line
                        INNER JOIN account_move move ON line.move_id = move.id
                         /* To use the exchange rate effective at the creation of the invoice. */
                         LEFT JOIN LATERAL (
                             SELECT rate
                               FROM res_currency_rate
                              WHERE company_id = line.company_id
                                AND currency_id = %(currency_id)s
                                AND name < line.date
                              ORDER BY name DESC
                              LIMIT 1
                         ) currency_rate
                           ON TRUE
                        WHERE move.state not in ('draft', 'cancel')
                            AND move.utm_reference IN %(utm_references)s
                            AND move.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')
                            AND move.company_id IN %(company_ids)s
                            AND line.account_id IS NOT NULL
                            AND line.display_type = 'product'
                        GROUP BY move.utm_reference
                        """
            self.env.cr.execute(
                query,
                {
                    'company_ids': tuple(self.env.companies.ids),
                    'currency_id': self.env.company.currency_id.id,
                    'utm_references': tuple(f'{post._name},{post.id}' for post in self),
                }
            )
            query_res = self.env.cr.dictfetchall()
            mapped_data = {datum['utm_reference']: datum['price_total_converted_sum'] for datum in query_res}

            for post in self:
                post.sale_invoiced_amount = mapped_data.get(f'{post._name},{post.id}', 0)
        else:
            for post in self:
                post.sale_invoiced_amount = 0

    def action_redirect_to_quotations(self):
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
        action['domain'] = [('utm_reference', 'in', [f'{post._name},{post.id}' for post in self])]
        action['context'] = {'create': False}
        return action

    def action_redirect_to_invoiced(self):
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_journal_line")
        action['context'] = {
            'create': False,
            'edit': False,
            'view_no_maturity': True
        }
        action['domain'] = [
            ('utm_reference', 'in', [f'{post._name},{post.id}' for post in self]),
            ('move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')),
            ('state', 'not in', ['draft', 'cancel'])
        ]
        return action
