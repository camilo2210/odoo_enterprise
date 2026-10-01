from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    in_company_ids = env["res.company"].search([("account_fiscal_country_id.code", "=", "IN")]).ids
    cr.execute(
        """
        UPDATE account_move am
           SET l10n_in_transaction_type = 'inter_state'
          FROM res_partner rp
         WHERE am.commercial_partner_id = rp.id
           AND am.move_type IN ('in_invoice', 'in_refund', 'in_receipt')
           AND am.l10n_in_transaction_type = 'intra_state'
           AND am.l10n_in_state_id != rp.state_id
           AND am.company_id = ANY(%s)
        """,
        [in_company_ids],
    )
