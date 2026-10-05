from odoo import api, models, _
from odoo.tools import BinaryBytes, file_open


class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    @api.model
    def get_appointment_type_templates_data(self):
        return super().get_appointment_type_templates_data() | {
            'paid_consultation': {
                'description': _("Let customers book a paid slot in your calendar with you"),
                'icon': '/appointment_account_payment/static/src/img/rfq.svg',
                'template_key': 'paid_consultation',
                'title': _("Paid Consultation"),
            },
            'paid_seats': {
                'description': _("Let customers book a fee per person for activities such as a theater, etc."),
                'icon': '/appointment_account_payment/static/src/img/chair.svg',
                'template_key': 'paid_seats',
                'title': _("Paid Seats"),
            },
        }

    @api.model
    def _get_appointment_type_template_values(self, template_key):
        if template_key == 'paid_consultation':
            return self._prepare_paid_consultation_template_values()
        elif template_key == 'paid_seats':
            return self._prepare_paid_seats_template_values()
        return super()._get_appointment_type_template_values(template_key)

    @api.model
    def _get_default_booking_product(self, product_name):
        with file_open('appointment_account_payment/static/src/img/booking_product.png', 'rb') as f:
            img = BinaryBytes(f.read())
        product_category = self.env.ref('product.product_category_services', raise_if_not_found=False)
        return self.env['product.product'].sudo().create({
            'name': product_name,
            'standard_price': 0.00,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'list_price': 50.00,
            'type': 'service',
            'purchase_ok': False,
            'categ_id': product_category.id if product_category else False,
            'image_1920': img,
        })

    @api.model
    def _prepare_paid_consultation_template_values(self):
        default_booking_product = self._get_default_booking_product(_("Paid Consultation Booking Fees"))
        return {
            'allow_guests': True,
            'appointment_duration': 0.5,
            'slot_creation_interval': 0.5,
            'is_auto_assign': True,
            'show_avatars': False,
            'event_videocall_source': False,
            'has_payment_step': True,
            'location_id': self.env.company.partner_id.id,
            'name': _('Paid Consultation'),
            'product_id': default_booking_product.id,
        }

    @api.model
    def _prepare_paid_seats_template_values(self):
        default_booking_product = self._get_default_booking_product(_("Paid Seats Booking Fees"))
        return {
            'appointment_duration': 1.0,
            'is_auto_assign': False,
            'is_date_first': True,
            'event_videocall_source': False,
            'has_payment_step': True,
            'location_id': self.env.company.partner_id.id,
            'max_schedule_days': 30,
            'name': _('Paid Seats'),
            'product_id': default_booking_product.id,
            'resource_ids': [
                (0, 0, {
                    'name': _('Room %s', number),
                    'capacity': capacity,
                }) for number, capacity in enumerate([5, 10, 15, 20], start=1)
            ],
            'manage_capacity': True,
            'schedule_based_on': 'resources',
            'staff_user_ids': [],
        }
