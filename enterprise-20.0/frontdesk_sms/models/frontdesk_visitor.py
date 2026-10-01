# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class FrontdeskVisitor(models.Model):
    _inherit = 'frontdesk.visitor'

    def _notify(self):
        super()._notify()
        for visitor in self:
            station = visitor.station_id
            host = visitor.host_id
            if not (station.host_selection and host):
                continue
            if station.notify_sms or (station.notify_discuss and not host.user_id and not station.notify_email and host.work_phone):
                visitor._notify_by_sms()

    def _notify_by_sms(self):
        self.ensure_one()
        host = self.host_id
        self._message_sms_with_template(
            template=self.station_id.sms_template_id,
            partner_ids=host.work_contact_id.ids if host.work_phone else [],
        )

    def _check_and_notify_visitor(self):
        super()._check_and_notify_visitor()
        odoobot = self.env.ref('base.partner_root')
        for visitor in self:
            phone = visitor.phone
            if not (phone and visitor.station_id.ask_phone):
                continue
            host = visitor.host_id
            if self._check_resources_leave(host.resource_id, visitor.check_in):
                body = visitor._prepare_unavailability_body(host)
                visitor._message_sms(
                    author_id=odoobot.id,
                    body=body,
                    sms_numbers=[phone],
                )
