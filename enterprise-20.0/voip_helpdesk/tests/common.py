from odoo.addons.helpdesk.tests.common import HelpdeskCommon


class VoipHelpdeskCommon(HelpdeskCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.helpdesk_manager.write({"login": "user_helpdesk_manager"})
        cls.helpdesk_user.write({"login": "user_helpdesk_user"})
        cls.partner.write({"phone": "110"})
        cls.ticket_open_1 = cls.env["helpdesk.ticket"].create({
            "name": "Open Ticket 1",
            "user_id": cls.helpdesk_user.id,
            "partner_id": cls.partner.id,
            "stage_id": cls.stage_progress.id,
        })
        cls.ticket_open_2 = cls.env["helpdesk.ticket"].create({
            "name": "Open Ticket 2",
            "user_id": cls.helpdesk_manager.id,
            "partner_id": cls.partner.id,
            "stage_id": cls.stage_new.id,
        })
        cls.ticket_open_3 = cls.env["helpdesk.ticket"].create({
            "name": "Open Ticket 3",
            "user_id": cls.helpdesk_manager.id,
            "partner_id": cls.partner.id,
            "stage_id": cls.stage_new.id,
        })
        cls.ticket_closed_1 = cls.env["helpdesk.ticket"].create({
            "name": "Closed Ticket 1",
            "user_id": cls.helpdesk_user.id,
            "partner_id": cls.partner.id,
            "stage_id": cls.stage_done.id,
        })
        cls.ticket_closed_2 = cls.env["helpdesk.ticket"].create({
            "name": "Closed Ticket 2",
            "user_id": cls.helpdesk_manager.id,
            "partner_id": cls.partner.id,
            "stage_id": cls.stage_cancel.id,
        })
        cls.call_1 = cls.env["voip.call"].create({
            "partner_id": cls.partner.id,
            "phone_number": "110",
            "user_id": cls.helpdesk_user.id,
        })
        cls.call_2 = cls.env["voip.call"].create({
            "partner_id": cls.partner.id,
            "phone_number": "110",
            "user_id": cls.helpdesk_manager.id,
        })
        cls.company_partner = cls.env['res.partner'].create({
            "name": "Company of Customer Credee",
        })
        cls.partner.parent_id = cls.company_partner
        cls.env["helpdesk.ticket"].create({
            "name": "Company Open Ticket",
            "user_id": cls.helpdesk_user.id,
            "partner_id": cls.company_partner.id,
            "stage_id": cls.stage_new.id,
        })
        cls.env["helpdesk.ticket"].create({
            "name": "Company Closed Ticket",
            "user_id": cls.helpdesk_user.id,
            "partner_id": cls.company_partner.id,
            "stage_id": cls.stage_done.id,
        })
