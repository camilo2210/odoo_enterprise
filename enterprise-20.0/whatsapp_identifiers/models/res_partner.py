import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # See docs for more details, especially the incoming message format
    # https://developers.facebook.com/documentation/business-messaging/whatsapp/business-scoped-user-ids/#incoming-messages-webhooks-1

    # Global unique id for a whatsapp user, only provided by the API if we contact the user using a phone number first
    wa_id = fields.Char(string='WhatsApp number identifier', help='Phone number as stored by WhatsApp', index='btree_not_null')
    # Business-scoped ids for a whatsapp user: one per account, as a BSUID is only valid for calls made
    # through the same WhatsApp account (or an account from the same business portfolio, which we don't model).
    # To be sudoed as needed since only useful technically, and only makes sense to access if one has access to the partner
    wa_bsuid_ids = fields.One2many('whatsapp.partner.bsuid', 'partner_id', string='WhatsApp Business-Scoped User IDs', groups='whatsapp.group_whatsapp_admin')
    wa_bsuid = fields.Char(string='Whatsapp Business-Scoped User ID', compute='_compute_wa_bsuid', compute_sudo=True, inverse='_inverse_wa_bsuid')

    @api.depends_context('whatsapp_account_id')
    @api.depends('wa_bsuid_ids')
    def _compute_wa_bsuid(self):
        wa_account_id = self.env.context.get('whatsapp_account_id')
        if isinstance(wa_account_id, self.env.registry['whatsapp.account']):
            wa_account_id = wa_account_id.id
        if not wa_account_id:
            self.wa_bsuid = ''
            return
        wa_bsuids = self.env['whatsapp.partner.bsuid'].search([('partner_id', 'in', self.ids), ('wa_account_id', '=', wa_account_id)])
        wa_bsuid_by_partner = {entry.partner_id: entry.bsuid for entry in wa_bsuids}
        for partner in self:
            partner.wa_bsuid = wa_bsuid_by_partner.get(partner, '')

    def _inverse_wa_bsuid(self):
        wa_account_id = self.env.context.get('whatsapp_account_id')
        if isinstance(wa_account_id, self.env.registry['whatsapp.account']):
            wa_account_id = wa_account_id.id
        if not wa_account_id:
            return
        wa_bsuids = self.env['whatsapp.partner.bsuid'].search([('partner_id', 'in', self.ids), ('wa_account_id', '=', wa_account_id)])
        bsuid_entry_by_partner = {entry.partner_id: entry for entry in wa_bsuids}
        to_create = []
        to_delete = []
        for partner in self:
            partner_bsuid = bsuid_entry_by_partner.get(partner)
            if not partner_bsuid and partner.wa_bsuid:
                to_create.append({'partner_id': partner.id, 'wa_account_id': wa_account_id, 'bsuid': partner.wa_bsuid})
            elif partner_bsuid and partner.wa_bsuid:
                partner_bsuid.bsuid = partner.wa_bsuid
            elif partner_bsuid and not partner.wa_bsuid:
                to_delete.append(partner_bsuid.id)
        self.env['whatsapp.partner.bsuid'].create(to_create)
        self.env['whatsapp.partner.bsuid'].browse(to_delete).unlink()

    def _find_from_whatsapp_identifiers(self, identifiers, wa_account_id=None):
        partner = super()._find_from_whatsapp_identifiers(identifiers, wa_account_id=wa_account_id)
        if not partner and (bsuid := identifiers.get('bsuid')):
            bsuid_domain = [('bsuid', '=', bsuid)]
            if wa_account_id:
                bsuid_domain.append(('wa_account_id', '=', wa_account_id.id))
            partner = self.env['whatsapp.partner.bsuid'].sudo().search(bsuid_domain, limit=1).partner_id
        if not partner and (wa_id := identifiers.get('wa_id')):
            partner = self.env['res.partner'].search([('wa_id', '=', wa_id)], limit=1)
        return partner

    def _get_create_values_from_whatsapp_identifiers(self, identifiers):
        partner_create_vals = super()._get_create_values_from_whatsapp_identifiers(identifiers)
        if bsuid := identifiers.get('bsuid'):
            country = self.env['res.country']
            split_bsuid = bsuid.split('.')
            if len(split_bsuid) == 2:
                country = self.env['res.country'].search([('code', '=', split_bsuid[0].upper())], limit=1)
                if country:
                    partner_create_vals['country_id'] = country.id
            else:
                _logger.warning('Unexpected format for bsuid: %s. No country could be fetched.', bsuid)
        if wa_id := identifiers.get('wa_id'):
            partner_create_vals['wa_id'] = wa_id
        return partner_create_vals

    def _update_from_whatsapp_identifiers(self, identifiers, wa_account_id):
        super()._update_from_whatsapp_identifiers(identifiers, wa_account_id)
        if bsuid := identifiers.get('bsuid'):
            self.with_context(whatsapp_account_id=wa_account_id).wa_bsuid = bsuid
        if wa_id := identifiers.get('wa_id'):
            self.wa_id = wa_id
