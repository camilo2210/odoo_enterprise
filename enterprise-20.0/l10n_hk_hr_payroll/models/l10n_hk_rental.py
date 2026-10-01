# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, MONTHLY

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.fields import Domain
from odoo.tools import float_round


class L10n_HkRental(models.Model):
    _name = 'l10n_hk.rental'
    _description = "Housing Benefit"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'

    # ------------------
    # Fields declaration
    # ------------------

    name = fields.Char(
        string="Rental Reference",
        required=True,
        compute='_compute_name',
        store=True,
        precompute=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    state_id = fields.Many2one(
        string="Region",
        comodel_name="res.country.state",
        domain=lambda self: [('country_id', '=', self.env.ref('base.hk').id)],
    )
    district = fields.Selection(
        selection=[
            # HK Island
            ("Central & Western", "Central & Western"),
            ("Wan Chai", "Wan Chai"),
            ("Eastern", "Eastern"),
            ("Southern", "Southern"),
            # Kowloon
            ("Yau Tsim Mong", "Yau Tsim Mong"),
            ("Sham Shui Po", "Sham Shui Po"),
            ("Kowloon City", "Kowloon City"),
            ("Wong Tai Sin", "Wong Tai Sin"),
            ("Kwun Tong", "Kwun Tong"),
            # NT
            ("Kwai Tsing", "Kwai Tsing"),
            ("Tsuen Wan", "Tsuen Wan"),
            ("Tuen Mun", "Tuen Mun"),
            ("Yuen Long", "Yuen Long"),
            ("North", "North"),
            ("Tai Po", "Tai Po"),
            ("Sha Tin", "Sha Tin"),
            ("Sai Kung", "Sai Kung"),
            ("Islands", "Islands"),
        ]
    )
    street = fields.Char(string="Street No. & Name")
    estate = fields.Char(string="Estate/Village")
    building = fields.Char(string="Building")
    block = fields.Char(string="Block/Tower")
    floor = fields.Char(string="Floor")
    flat = fields.Char(string="Flat/Unit")
    address = fields.Char(
        compute='_compute_address',
        store=True,
        readonly=False,
        tracking=True,
    )
    landlord_name = fields.Char(
        string="Landlord Name",
        help="Name of the landlord, as appearing on the lease agreement and rental payments.",
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], default='draft', required=True, copy=False, readonly=True, tracking=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        domain="['|', ('company_id', '=', False), ('company_id', 'in', allowed_company_ids)]",
        required=True,
        tracking=True,
    )
    date_start = fields.Date(
        'Start Date', required=True, default=fields.Date.context_today, index=True)
    date_end = fields.Date('End Date')
    valid_up_to_date = fields.Date(
        string='Proof Expiry Date',
        help='Set this date to the end of the currently submitted rental receipt validity to avoid reimbursing by mistake.',
        tracking=True,
    )
    amount = fields.Monetary(
        string="Rental Amount",
        required=True,
        help="The amount of the rental, as it appears on the lease.",
        tracking=True,
    )
    monthly_rent_amount = fields.Monetary(
        compute='_compute_monthly_rent_amount',
        store=True,
        readonly=False,
        help="The actual amount paid monthly by the employee, or the limit of the reimbursement if any.",
        tracking=True,
    )
    co_pay_amount = fields.Monetary(
        help="Employee contribution to the rental amount.",
        tracking=True,
    )
    nature = fields.Selection(
        selection=[
            ('FLAT/HOUSE', 'Flat/House'),
            ('SERVICED APARTMENT', 'Serviced Apartment'),
            ('HOTEL/HOSTEL:1 RM', 'Hotel/Hostel 1 Room'),
            ('HOTEL/HOSTEL:2 RM', 'Hotel/Hostel 2 Rooms'),
            ('HOTEL/HOSTEL:>2 RM', 'Hotel/Hostel > 2 Rooms'),
            ('BOARDING HSE:1 RM', 'Boarding House 1 Room'),
            ('BOARDING HSE:2 RM', 'Boarding House 2 Rooms'),
            ('BOARDING HSE:>2 RM', 'Boarding House > 2 Rooms'),
        ], string='Nature', default='FLAT/HOUSE', required=True)
    company_id = fields.Many2one(
        related='employee_id.company_id',
        required=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
    )
    rentals_count = fields.Integer(related='employee_id.l10n_hk_rentals_count')
    lease_type = fields.Selection(
        selection=[
            ('reimbursement', 'Employee pays, Company refunds'),
            ('direct_payment', 'Company pays Landlord'),
            ('co_payment', 'Company pays, Employee contributes'),
        ],
        default='reimbursement', required=True,
        tracking=True,
    )
    lease_agreement_file = fields.Binary(
        attachment=True,
        string="Lease Agreement File",
        copy=False,
    )
    stamped_duty_file = fields.Binary(
        attachment=True,
        string="Stamped Duty File",
        copy=False,
    )
    similar_rental_ids = fields.One2many(
        comodel_name='l10n_hk.rental',
        compute='_compute_similar_rental_ids',
    )
    similar_rentals_count = fields.Integer(
        compute='_compute_similar_rental_ids',
    )
    similar_rentals_monthly_rent_too_high = fields.Boolean(
        compute='_compute_similar_rental_ids',
    )
    is_hr_user = fields.Boolean(
        compute='_compute_is_hr_user',
    )

    # --------------------------------
    # Compute, inverse, search methods
    # --------------------------------

    @api.depends('amount', 'lease_type')
    def _compute_monthly_rent_amount(self):
        """
        By default, we set the full amount, but we allow lowering it. (Company limit, sharing of a single rental, ...)
        """
        for rental in self.filtered(lambda r: r.lease_type == 'reimbursement'):
            rental.monthly_rent_amount = rental.amount

    @api.depends('state_id', 'district', 'street', 'estate', 'building', 'block', 'floor', 'flat')
    def _compute_address(self):
        """
        We are using separate fields but building a address string for a few reasons:
        - It helps standardize the format for later reporting
        - By using a standard format, we can detect duplicate/shared rentals/... and apply some constraints
        - It helps avoid missing a part/...

        The address is formated as recommended by the Hong Kong Post, from the smallest entity to the largest.
        Note that the length of the address string is limited when reporting to IRD, so we use some abbreviation to save
        a bit of space.
        """
        for rental in self:
            floor = (rental.floor or '').strip().upper()
            # It is standard to use xx/F, but this doesn't apply to all cases.
            if floor.isdigit():
                floor = f"{floor}/F"
            elif floor == 'G':
                floor = "G/F"

            flat = (rental.flat or '').strip().upper()
            if flat and len(flat) < 5 and not flat.startswith(('FLAT', 'UNIT', 'ROOM', 'SUITE', 'HOUSE')):
                flat = f"RM {flat}"

            block = (rental.block or '').strip().upper()
            if block and (block.isdigit() or (len(block) == 1 and block.isalnum())):
                block = f"BLK {block}"

            parts = [
                flat,
                floor,
                block,
                (rental.building or '').strip().upper(),
                (rental.estate or '').strip().upper(),
                (rental.street or '').strip().upper(),
                (rental.district or '').strip().upper(),
                (rental.state_id.name or '').upper(),
            ]

            # The fallback is there to avoid replacing an address string (from previous versions, or manually set)
            # By an empty computed address.
            rental.address = ", ".join(list(filter(None, parts))) or rental.address

    @api.depends('employee_id', 'building', 'flat')
    def _compute_name(self):
        for rental in self:
            name = rental.employee_id.name
            if rental.building:
                name += f" - {rental.building}"
            rental.name = name

    @api.depends('address')
    def _compute_similar_rental_ids(self):
        # It's ok to search in the loop, we only ever compute this when opening the rental's form view
        for rental in self:
            empty_address_fields = not rental.building and not rental.floor and not rental.flat and not rental.district and not rental.state_id
            if not rental.address or empty_address_fields:
                rental.update({
                    'similar_rental_ids': False,
                    'similar_rentals_count': False,
                    'similar_rentals_monthly_rent_too_high': False,
                })
            else:
                domain = Domain([
                    ('id', 'not in', rental.ids),
                    ('active', '=', True),
                    ('building', '=ilike', rental.building),
                    ('floor', '=ilike', rental.floor),
                    ('flat', '=ilike', rental.flat),
                    ('district', '=', rental.district),
                    ('state_id', '=', rental.state_id.id),
                    ('address', '!=', False),
                    ('employee_id', '!=', rental.employee_id.id),
                    '|',
                    ('date_end', '=', False),
                    ('date_end', '>=', rental.date_start)
                ])
                if rental.date_end:
                    domain &= Domain('date_start', '<=', rental.date_end)
                if rental.block:
                    domain &= Domain('block', '=ilike', rental.block)
                else:
                    domain &= Domain('block', '=', False)
                similar_rentals = self.env['l10n_hk.rental'].search(domain)
                rental.update({
                    'similar_rental_ids': similar_rentals,
                    'similar_rentals_count': len(similar_rentals),
                    'similar_rentals_monthly_rent_too_high': (sum((rental | similar_rentals).mapped('monthly_rent_amount'))) > rental.amount,
                })

    @api.depends_context('uid')
    def _compute_is_hr_user(self):
        self.is_hr_user = self.env.user.has_group('hr.group_hr_user')

    # ----------------------------
    # Onchange, Constraint methods
    # ----------------------------

    @api.onchange('lease_type')
    def _onchange_lease_type(self):
        """
        Avoid issues by ensuring we reset the unused monthly rent amount when not using the reimbursement flow.
        In case of switching back and forth, we reset the monthly amount back to the amount field as well.
        """
        if self.lease_type != 'reimbursement':
            self.monthly_rent_amount = 0
        else:
            self.monthly_rent_amount = self.amount

    @api.constrains('employee_id', 'state', 'date_start', 'date_end')
    def _check_current_rental(self):
        for rental in self.filtered(lambda r: r.state == 'confirmed'):
            domain = Domain([
                ('id', '!=', rental.id),
                ('employee_id', '=', rental.employee_id.id),
                ('state', '=', 'confirmed'),
                '|',
                ('date_end', '>=', rental.date_start),
                ('date_end', '=', False),
            ])
            if rental.date_end:
                domain &= Domain('date_start', '<=', rental.date_end)

            if self.search_count(domain, limit=1):
                raise ValidationError(rental.env._(
                    'Rental %(rental)s: employee %(employee)s already has a rental running during this period.',
                    rental=rental.name, employee=rental.employee_id.name,
                ))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rental in self:
            if rental.date_end and rental.date_start > rental.date_end:
                raise ValidationError(rental.env._(
                    'Rental %(rental)s: start date (%(start)s) must be earlier than rental end date (%(end)s).',
                    rental=rental.name, start=rental.date_start, end=rental.date_end,
                ))

    @api.constrains('amount', 'monthly_rent_amount')
    def _check_amounts(self):
        for rental in self:
            if rental.monthly_rent_amount > rental.amount:
                raise ValidationError(rental.env._(
                    'The rental %(rental_name)s cannot have a monthly rent amount (%(monthly_rent_amount)s) higher than the amount (%(amount)s).',
                    rental_name=rental.name, monthly_rent_amount=rental.monthly_rent_amount, amount=rental.amount,
                ))

    @api.ondelete(at_uninstall=False)
    def _unlink_if_running(self):
        for rental in self:
            if rental.state != 'draft':
                raise UserError(rental.env._("You cannot delete the rental %(rental_name)s as it is no longer a draft. Please archive it instead.", rental_name=rental.name))

    # -----------------------
    # CRUD, inherited methods
    # -----------------------

    def action_attach_payment_proofs(self, **kwargs):
        """When attachments are uploaded as payment proofs, make sure to send a message to concerned parties to notify them about it."""
        self.ensure_one()
        if not self.has_access('write'):
            raise AccessError(self.env._("You don't have the access rights to modify this rental."))

        attachment_ids = [attachment_id for attachment_id in kwargs.get('attachment_ids', []) if attachment_id]
        attachments = self.env['ir.attachment'].browse(attachment_ids)
        if len(attachments) == 1:
            message_body = self.env._('The rental "%(rental_name)s" has received a new payment proof.', rental_name=self.name)
        else:
            message_body = self.env._('The rental "%(rental_name)s" has received new payment proofs.', rental_name=self.name)

        self.message_post(
            body=message_body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            attachments=[(attachment.name, attachment.raw.content) for attachment in attachments]
        )

    def write(self, vals):
        # Quick check to block non hr users from writing on anything.
        if not self.env.user.has_group('hr.group_hr_user') and vals:
            raise AccessError(self.env._('You are not allowed to edit this rental.'))
        return super().write(vals)

    # --------------
    # Action methods
    # --------------

    def action_reset_to_draft(self):
        self.filtered(lambda rental: rental.state == 'confirmed').state = 'draft'

    def action_confirm_rental(self):
        """
        Move the rental(s) to the running stage.
        We will also ensure that the relevant persons are subscribed to the document so that they can be notified of important changes.
        As an important one-time event, a message is also posted so that followers are notified of the approval being done.
        """
        rentals_to_confirm = self.filtered(lambda rental: rental.state == 'draft')
        for rental in rentals_to_confirm:
            partners_to_subscribe = set()
            partners_to_subscribe.add(rental.employee_id.version_id.hr_responsible_id.partner_id.id)
            if rental.employee_id.user_partner_id:
                partners_to_subscribe.add(rental.employee_id.user_partner_id.id)
            rental.with_context(mail_post_autofollow=True).message_post(
                body=rental.env._('The rental "%(rental_name)s" has been approved and is now running.', rental_name=rental.name),
                partner_ids=list(partners_to_subscribe),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        rentals_to_confirm.state = 'confirmed'

    def action_open_similar_rentals_list(self):
        self.ensure_one()
        return self.similar_rental_ids._get_records_action(name=self.env._("Similar Rentals"))

    # ----------------
    # Business methods
    # ----------------

    @api.model
    def _cron_send_reminder(self):
        """
        Help send reminders to employees that did not submit a proof yet for this month.
        We ignore rentals whose valid up to date was never set.
        """
        today = fields.Date.context_today(self)
        concerned_rentals = self.env['l10n_hk.rental'].search([
            ('state', '=', 'confirmed'),
            ('lease_type', '=', 'reimbursement'),
            ('valid_up_to_date', '!=', False),
            ('valid_up_to_date', '<', today + relativedelta(day=1)),
            '|',
            ('date_end', '=', False),
            ('date_end', '>', today),
        ])
        for rental in concerned_rentals:
            template = self.env.ref(
                xml_id='l10n_hk_hr_payroll.mail_template_rental_proof_reminder',
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(rental.id, email_layout_xmlid='mail.mail_notification_light')

    def _get_rent_amount_in_period(self, period_start, period_end):
        """
        Calculates the total rent paid during the intersection of the rental period
        and the reporting period.
        Ensure that we calculate the exact paid amount based on the days of each month.
        """
        self.ensure_one()
        employee_start_date = self.employee_id._get_first_version_date()
        employee_departure_date = self.employee_id.departure_date
        active_start = max(self.date_start, period_start, employee_start_date)
        active_end = min(self.date_end or period_end, period_end, employee_departure_date or period_end)
        total_rent = 0.0
        if active_start > active_end:
            return total_rent

        start_iter = active_start.replace(day=1)
        for dt in rrule(MONTHLY, dtstart=start_iter, until=active_end):
            current_month_start = dt.date()
            current_month_end = current_month_start + relativedelta(day=31)
            overlap_start = max(active_start, current_month_start)
            overlap_end = min(active_end, current_month_end)

            days_active = (overlap_end - overlap_start).days + 1
            daily_rate = self.amount / current_month_end.day
            total_rent += (daily_rate * days_active)

        return int(float_round(total_rent, precision_digits=2))
