# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class FrontdeskVisitor(models.Model):
    _inherit = 'frontdesk.visitor'

    def _get_whatsapp_safe_fields(self):
        return {'name', 'phone', 'station_id.name'}

    def _notify(self):
        super()._notify()
        for visitor in self:
            station = visitor.station_id
            host = visitor.host_id
            if not (station.host_selection and host):
                continue
            if station.notify_whatsapp or (not host.user_id and host.work_phone and station.notify_discuss and not station.notify_email and 'notify_sms' not in station._fields):
                visitor._notify_by_whatsapp()

    def _notify_by_whatsapp(self):
        self.ensure_one()
        whatsapp_template = self.station_id.whatsapp_template_id
        host = self.host_id
        if not (whatsapp_template and host.work_phone):
            return
        phone = host._phone_format(number=host.work_phone) or host.work_phone
        self.env['whatsapp.composer'].create({
            'res_ids': self.ids,
            'res_model': 'frontdesk.visitor',
            'wa_template_id': whatsapp_template.id,
            'phone': phone,
        })._send_whatsapp_template()

    def _check_and_notify_visitor(self):
        super()._check_and_notify_visitor()
        wa_account = self.env['whatsapp.account'].search([], limit=1)
        if not wa_account:
            return
        odoobot = self.env.ref('base.partner_root')
        for visitor in self:
            if not (visitor.phone and visitor.station_id.ask_phone):
                continue
            host = visitor.host_id
            if self._check_resources_leave(host.resource_id, visitor.check_in):
                phone = visitor._phone_format(number=visitor.phone) or visitor.phone
                mail_message = visitor.message_post(
                    body=visitor._prepare_unavailability_body(host),
                    author_id=odoobot.id,
                    message_type='whatsapp_message',
                    subtype_xmlid='mail.mt_note',
                )
                self.env['whatsapp.message'].create({
                    'mail_message_id': mail_message.id,
                    'mobile_number': phone,
                    'mobile_number_formatted': visitor._whatsapp_phone_format(number=phone) or phone,
                    'wa_account_id': wa_account.id,
                })._send()
