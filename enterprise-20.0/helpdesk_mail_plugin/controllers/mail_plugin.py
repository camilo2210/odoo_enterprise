# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request, route

from odoo.addons.mail_plugin.controllers import mail_plugin
from odoo.fields import Domain
from odoo.tools.image import image_data_uri


class MailPluginController(mail_plugin.MailPluginController):
    def _search_records(self, model, terms, limit=30):
        if model == "helpdesk.ticket":
            domain = Domain.OR([('name', 'ilike', term)] for term in terms)
            return self._search_and_format_tickets(domain, limit=limit)
        return super()._search_records(model, terms, limit)

    def _get_contact_data(self, partner, email, **kwargs):
        """
        Return the tickets key only if the current user can create tickets. So, if they can not
        create tickets, the section won't be visible on the addin side (like if the Helpdesk
        module was not installed on the database).
        """
        contact_values = super()._get_contact_data(partner, email, **kwargs)

        if not request.env['helpdesk.ticket'].has_access('create'):
            return contact_values

        if partner:
            contact_values['tickets'], contact_values['ticket_count'] = \
                self._search_and_format_tickets([('partner_id', '=', partner.id)])
        else:
            contact_values['tickets'], contact_values['ticket_count'] = [], 0

        return contact_values

    def _search_and_format_tickets(self, domain, limit=30):
        """Add the tickets related to the partner."""
        ticket_count = request.env['helpdesk.ticket'].search_count(domain)
        tickets = request.env['helpdesk.ticket'].search(
            domain,
            limit=limit,
            order='close_date DESC, priority DESC',
        )
        return [self._format_ticket(ticket) for ticket in tickets], ticket_count

    def _mail_models_access_whitelist(self, access):
        models_whitelist = super()._mail_models_access_whitelist(access)
        if not request.env['helpdesk.ticket'].has_access(access):
            return models_whitelist
        return models_whitelist + ['helpdesk.ticket']

    def _translation_modules_whitelist(self):
        modules_whitelist = super()._translation_modules_whitelist()
        if not request.env['helpdesk.ticket'].has_access('create'):
            return modules_whitelist
        return modules_whitelist + ['helpdesk_mail_plugin']

    @route('/mail_plugin/ticket/create', type='jsonrpc', auth='outlook', cors="*")
    def helpdesk_ticket_create(
        self, partner_id, partner_name, partner_email,
        email_body, email_subject, attachments=None):
        if partner_id:
            partner = request.env['res.partner'].browse(partner_id).exists()
            if not partner:
                return {'error': 'partner_not_found'}
        else:
            partner = self._search_or_create_partner(partner_email, partner_name)

        ticket = request.env['helpdesk.ticket'].with_company(partner.company_id).create({
            'name': email_subject,
            'partner_id': partner.id,
            'description': email_body,
            'user_id': request.env.uid,
            # we don't rely on default values because we want to trigger the ticket acknowledgement email
            # there is an advanced processing on the "create" method to determine the stage based on the team
            # (see 'helpdesk.ticket#create' and 'helpdesk.ticket#_track_template')
            'team_id': request.env['helpdesk.ticket']._default_team_id(),
        })
        if attachments:
            request.env["ir.attachment"].create([{
                "name": name,
                "raw": content,
                "res_model": ticket._name,
                "res_id": ticket.id,
            } for name, content in attachments])
        values = self._format_ticket(ticket)
        values['partner_id'] = ticket.partner_id.id
        values['partner_image'] = image_data_uri(partner.avatar_128)
        return values

    def _format_ticket(self, ticket):
        return {
            'id': ticket.id,
            'name': ticket.display_name,
            'stage_name': ticket.stage_id.name,
        }
