from odoo import _, api, fields, models
from odoo.addons.whatsapp.tools.whatsapp_api import WhatsAppApi
from odoo.addons.whatsapp.tools.whatsapp_exception import WhatsAppError


class WhatsappBlocklist(models.Model):
    _name = 'whatsapp.blocklist'
    _inherit = ['mail.thread']
    _description = 'WhatsApp Blocklist'
    _order = 'wa_account_id, id desc'
    _rec_name = 'number'

    @api.model
    def _get_default_wa_account_id(self):
        first_account = self.env['whatsapp.account'].search(
            [('allowed_company_ids', 'in', self.env.companies.ids)], limit=1)
        return first_account.id if first_account else False

    number = fields.Char(
        string="WhatsApp Number", required=True, search='_search_number',
        tracking=1, help="Number should be E164 formatted")
    active = fields.Boolean(default=True)
    wa_account_id = fields.Many2one(
        comodel_name='whatsapp.account', string="WhatsApp Account", required=True,
        ondelete='cascade', tracking=2, default=_get_default_wa_account_id)

    _unique_number_per_account = models.Constraint(
        'unique (number, wa_account_id)',
        "Number already exists for this WhatsApp account",
    )

    def _search_number(self, operator, value):
        sanitize = self.env.user._phone_format
        if operator in ('in', 'not in'):
            value = [sanitize(number=number) or number for number in value]
        else:
            value = sanitize(number=value) or value
        return [('number', operator, value)]

    @api.model_create_multi
    def create(self, vals_list):
        """Create new (or activate existing) blocklisted numbers.

        Attempting to create an existing inactive blocklist entry reactivates it,
        unless active=False is explicitly requested. Existing active records are
        returned and not recreated.

        Returns the union of created and existing blocklist records in the same
        order as requested.
        """
        # Normalize numbers, discard duplicate (wa_account_id, number) pairs,
        # and collect the unique account ids and numbers for the lookup.
        to_create = []
        processed_keys = set()
        numbers = set()
        wa_account_ids = set()
        for vals in vals_list:
            number = self.env.user._phone_format(number=vals['number'], raise_exception=True)
            wa_account_id = vals['wa_account_id']
            key = (wa_account_id, number)
            if key in processed_keys:
                continue

            to_create.append(dict(vals, number=number))
            processed_keys.add(key)
            numbers.add(number)
            wa_account_ids.add(wa_account_id)

        # Fetch existing blocklist entries, including archived ones.
        existing_records = self.with_context(active_test=False).search([
            ('wa_account_id', 'in', wa_account_ids),
            ('number', 'in', numbers),
        ])

        # Reactivate archived records unless they were explicitly requested to remain inactive.
        inactive_requested_keys = {(vals['wa_account_id'], vals['number']) for vals in to_create if not vals.get('active', True)}
        records_to_unarchive = existing_records.filtered(
            lambda record: not record.active
            and (record.wa_account_id.id, record.number) not in inactive_requested_keys
        )
        if records_to_unarchive:
            records_to_unarchive.action_unarchive()

        # Create only records that do not already exist.
        existing_record_keys = {(record.wa_account_id.id, record.number) for record in existing_records}
        vals_to_create = [vals for vals in to_create if (vals['wa_account_id'], vals['number']) not in existing_record_keys]
        created_records = super().create(vals_to_create)

        # Block newly created numbers and archive those that could not be blocked.
        if created_records:
            blocked_records = created_records._action_update_block_status('block')
            (created_records - blocked_records).active = False

        # Return records in the same order as requested, including reused entries.
        records_by_key = {(record.wa_account_id.id, record.number): record for record in existing_records | created_records}
        return self.browse(records_by_key[vals['wa_account_id'], vals['number']].id for vals in to_create)

    def write(self, vals):
        if 'number' in vals:
            vals['number'] = self.env.user._phone_format(number=vals['number'], raise_exception=True)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_and_unblock(self):
        self._action_update_block_status('unblock')

    def action_archive(self):
        unblocked_records = self._action_update_block_status('unblock')
        to_archive = self.filtered(lambda record: record in unblocked_records)
        return super(WhatsappBlocklist, to_archive).action_archive()

    def action_unarchive(self):
        blocked_records = self._action_update_block_status('block', records_active_state=False)
        to_unarchive = self.filtered(lambda record: record in blocked_records)
        return super(WhatsappBlocklist, to_unarchive).action_unarchive()

    def button_block_number(self):
        self.ensure_one()
        self._action_update_block_status('block', records_active_state=False).active = True

    def button_unblock_number(self):
        self.ensure_one()
        self._action_update_block_status('unblock').active = False

    def _action_update_block_status(self, operation, records_active_state=True):
        updated_records = self.env['whatsapp.blocklist']
        records_by_account = self._read_group(
            domain=[('id', 'in', self.ids), ('active', '=', records_active_state)],
            groupby=['wa_account_id'],
            aggregates=['id:recordset'],
        )
        if not records_by_account:
            self.env.user._bus_send('simple_notification', {
                'type': 'warning',
                'title': _("No numbers to update"),
                'message': _(
                    "All selected numbers are already %(state_label)s.",
                    state_label=_("blocked") if operation == 'block' else _("unblocked")
                ),
            })
            return updated_records

        for wa_account_id, records in records_by_account:
            wa_api = WhatsAppApi(wa_account_id)
            numbers_to_operate = records.mapped('number')
            try:
                result = wa_api._update_block_status(operation, numbers_to_operate)
            except WhatsAppError as err:
                self.env.user._bus_send('simple_notification', {
                    'type': 'danger',
                    'message': _(
                        "Account [%(account)s]: Failed to %(operation)s %(count)d %(number_word)s: %(error)s",
                        account=wa_account_id.name,
                        operation_label=_("block") if operation == 'block' else _("unblock"),
                        count=len(numbers_to_operate),
                        number_word=_("number") if len(numbers_to_operate) <= 1 else _("numbers"),
                        error=str(err),
                    ),
                })
                continue

            updated_count, failed_count = len(result['updated_numbers']), len(result['failures'])
            if failed_count and not updated_count:
                notify_type = 'danger'
            elif failed_count:
                notify_type = 'warning'
            else:
                notify_type = 'success'
            self.env.user._bus_send('simple_notification', {
                'type': notify_type,
                'message': _(
                    "Account [%(account)s]: %(updated_count)d %(state_label)s, %(failed_count)d failed.",
                    account=wa_account_id.name,
                    failed_count=failed_count,
                    updated_count=updated_count,
                    state_label=_("blocked") if operation == 'block' else _("unblocked"),
                ),
            })
            updated_records |= records.filtered(lambda record: record.number in result['updated_numbers'])
        return updated_records
