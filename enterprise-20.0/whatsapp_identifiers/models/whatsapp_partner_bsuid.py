from odoo import fields, models


class WhatsappPartnerBsuid(models.Model):
    """A WhatsApp Business-Scoped User ID for a partner, scoped to a WhatsApp Business Account.

    Each whatsapp user is identified by a BSUID but as this is scoped to the business portfolio of the account
    we need to store it for each account, hence this table.
    """

    _name = 'whatsapp.partner.bsuid'
    _description = 'WhatsApp Business-Scoped User ID'
    _rec_name = 'bsuid'

    partner_id = fields.Many2one('res.partner', string='Partner', required=True, ondelete='cascade', index=True)
    wa_account_id = fields.Many2one('whatsapp.account', string='WhatsApp Account', required=True, ondelete='cascade', index=True)
    bsuid = fields.Char(string='Business-Scoped User ID', required=True, index=True)

    _uniq_account_bsuid = models.Constraint(
        'unique(wa_account_id, bsuid, partner_id)',
        'A Business-Scoped User ID must be unique per WhatsApp account per partner.',
    )
