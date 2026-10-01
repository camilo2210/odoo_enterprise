from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    in_company_ids = env["res.company"].search([("account_fiscal_country_id.code", "=", "IN")]).ids
    cr.execute(
        """
        UPDATE account_move am
           SET l10n_in_transaction_type = CASE
                   WHEN am.l10n_in_state_id = company_rp.state_id
                   THEN 'intra_state'
                   ELSE 'inter_state'
               END
          FROM account_journal aj,
               res_company rc
          JOIN res_partner company_rp ON rc.partner_id = company_rp.id
         WHERE am.journal_id = aj.id
           AND am.company_id = rc.id
           AND am.l10n_in_state_id IS NOT NULL
           AND am.company_id = ANY(%s)
           AND aj.type NOT IN ('sale', 'purchase')
        """,
        [in_company_ids],
    )
