# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup, escape
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _, Command


class HrContractSignDocumentWizard(models.TransientModel):
    _name = 'hr.contract.sign.document.wizard'
    _description = 'Sign document in contract'

    def _group_hr_contract_domain(self):
        group = self.env.ref('hr.group_hr_manager', raise_if_not_found=False)
        return [('all_group_ids', 'in', group.ids)] if group else []

    def _get_sign_template_ids(self):
        list_template = self.env['sign.template']
        for template in self.env['sign.template'].search([]):
            distinct_responsible_count = len(template.sign_item_ids.mapped('responsible_id'))
            if distinct_responsible_count == 2 or distinct_responsible_count == 1:
                list_template |= template
        return list_template

    def _default_get_template_warning(self):
        return not bool(self._get_sign_template_ids()) and _('No documents templates on the database.')

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        if 'responsible_id' in fields and not defaults.get('responsible_id') and defaults.get('version_id'):
            contract = self.env['hr.version'].browse(defaults.get('version_id'))
            defaults['responsible_id'] = contract.hr_responsible_id
        else:
            defaults['responsible_id'] = self.env.user
        active_model = self.env.context.get('active_model', '')
        if active_model == 'hr.version':
            defaults['version_id'] = self.env.context.get('active_id')
        elif active_model == 'hr.employee':
            defaults['employee_ids'] = [Command.set(self.env.context.get('active_ids'))]
        return defaults

    version_id = fields.Many2one(
        'hr.version', string='Contract',
        compute='_compute_contract_id', store=True, readonly=False)
    employee_ids = fields.Many2many(
        'hr.employee', string='Employees',
        compute='_compute_employee_ids', store=True, readonly=False)
    responsible_id = fields.Many2one('res.users', string='Responsible', domain=_group_hr_contract_domain)
    employee_role_id = fields.Many2one(
        "sign.item.role", string="Employee Role",
        required=True, domain="[('id', 'in', sign_template_responsible_ids)]",
        compute='_compute_employee_role_id', store=True, readonly=False,
        help="Employee's role on the templates to sign. The same role must be present in all the templates")
    sign_template_responsible_ids = fields.Many2many(
        'sign.item.role', compute='_compute_responsible_ids')
    possible_template_ids = fields.Many2many('sign.template', compute='_compute_possible_template_ids')
    sign_template_ids = fields.Many2many(
        'sign.template', string='Documents to sign',
        domain="[('id', 'in', possible_template_ids)]", help="""Select only documents with either 1 or 2 different signatories.
        Documents with 1 signatory require only the employee's signature, while those with 2 signatories require signatures from both the employee and the HR responsible.
        """, required=True)
    has_both_template = fields.Boolean(compute='_compute_has_both_template')
    template_warning = fields.Char(default=_default_get_template_warning, store=False)
    signing_employee = fields.Selection([
        ('employee', 'Employee'),
        ('hr_responsible', 'HR Responsible'),
    ], default='employee', help="Choose who will sign the document when the selected template has a single signer.")

    subject = fields.Char(string="Subject", required=True, default='Signature Request')
    message = fields.Html("Message")
    cc_partner_ids = fields.Many2many('res.partner', string="Copy to")
    attachment_ids = fields.Many2many('ir.attachment', bypass_search_access=True)
    mail_to = fields.Selection([
        ('work', 'Work'),
        ('private', 'Private'),
    ], string='Email', help="""Email used to send the signature request.
                - Work takes the email defined in "work email"
                - Private takes the email defined in Private Information
                - If the selected email is not defined, the available one will be used.""", default='work')
    mail_displayed = fields.Char(compute='_compute_mail_displayed')
    is_single_signer = fields.Boolean(compute='_compute_is_single_signer')
    show_sign_now = fields.Boolean(compute='_compute_show_sign_now')

    @api.depends('sign_template_responsible_ids')
    def _compute_employee_role_id(self):
        for wizard in self:
            if wizard.employee_role_id not in wizard.sign_template_responsible_ids:
                wizard.employee_role_id = False
            if len(wizard.sign_template_responsible_ids) == 1:
                wizard.employee_role_id = wizard.sign_template_responsible_ids._origin

    @api.depends('sign_template_ids.sign_item_ids.responsible_id')
    def _compute_responsible_ids(self):
        for r in self:
            responsible_ids = self.env['sign.item.role']
            for sign_template_id in r.sign_template_ids:
                if responsible_ids:
                    responsible_ids &= sign_template_id.sign_item_ids.responsible_id
                else:
                    responsible_ids |= sign_template_id.sign_item_ids.responsible_id
            r.sign_template_responsible_ids = responsible_ids

    @api.depends('sign_template_ids')
    def _compute_possible_template_ids(self):
        possible_sign_templates = self._get_sign_template_ids()
        for wizard in self:
            if not wizard.sign_template_ids:
                wizard.possible_template_ids = possible_sign_templates
            else:
                role_count = len(wizard.sign_template_ids[:1].sign_item_ids.responsible_id)
                wizard.possible_template_ids = possible_sign_templates.filtered(lambda t: len(t.sign_item_ids.responsible_id) == role_count)

    @api.depends('version_id')
    def _compute_employee_ids(self):
        for wizard in self:
            if wizard.version_id:
                wizard.employee_ids |= wizard.version_id.employee_id

    @api.depends('employee_ids')
    def _compute_contract_id(self):
        for wizard in self:
            if wizard.version_id.employee_id not in wizard.employee_ids:
                wizard.version_id = False

    @api.depends('sign_template_ids')
    def _compute_has_both_template(self):
        for wizard in self:
            wizard.has_both_template = bool(wizard.sign_template_ids.filtered(lambda t: len(t.sign_item_ids.mapped('responsible_id')) == 2))

    @api.depends('employee_ids', 'mail_to')
    def _compute_mail_displayed(self):
        for wizard in self:
            if len(wizard.employee_ids) == 1:
                wizard.mail_displayed = wizard.employee_ids.private_email if self.mail_to == 'private' else wizard.employee_ids.work_email
            else:
                wizard.mail_displayed = False

    @api.depends('sign_template_responsible_ids')
    def _compute_is_single_signer(self):
        """ Compute whether the selected templates have a single signer to show the fields. """
        for wizard in self:
            wizard.is_single_signer = len(wizard.sign_template_responsible_ids) == 1

    @api.depends('employee_ids', 'sign_template_ids', 'signing_employee')
    def _compute_show_sign_now(self):
        """ Compute whether the 'Sign Now' button should be shown. """
        for wizard in self:
            wizard.show_sign_now = (
                wizard.is_single_signer
                and len(wizard.employee_ids) == 1
                and len(wizard.sign_template_ids) == 1
                and wizard.signing_employee == 'hr_responsible'
            )

    @api.onchange('employee_ids', 'signing_employee')
    def _onchange_cc_partner_ids(self):
        """ Update the CC recipients based on the selected signer.

        Employees are added to CC when the HR responsible signs the document and
        removed when the employee is the signer.
        """
        employee_contacts = self.employee_ids.mapped('work_contact_id')

        if self.signing_employee == 'hr_responsible':
            self.cc_partner_ids |= employee_contacts
        else:
            self.cc_partner_ids -= employee_contacts

    def validate_signature(self, sign_now=False):
        """ Validate the signature request and create/send the sign document.

        :param bool sign_now: If ``True``, the document is prepared for immediate
            signing by the current user instead of only creating the signature
            request and sending it to the recipients.
        """
        self.ensure_one()
        # Partner by employee
        partner_by_employee = dict()
        email_by_employee = dict()
        for employee in self.employee_ids:
            email_choice = employee.private_email if self.mail_to == "private" else employee.work_email
            if email_choice:
                email_used = email_choice
            else:
                message_display = _("%s does not have a private email set.", employee.name) if self.mail_to == "private" else _("%s does not have a work email set.", employee.name)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': message_display,
                        'sticky': False,
                        'type': 'danger',
                    }
                }
            partner_by_employee[employee] = employee.work_contact_id
            email_by_employee[employee] = email_used

        sign_request = self.env['sign.request']
        if not self.browse().has_access('create'):
            sign_request = sign_request.sudo()

        sign_values = []
        sign_templates_employee_ids = self.sign_template_ids.filtered(lambda t: len(t.sign_item_ids.mapped('responsible_id')) == 1)
        sign_templates_both_ids = self.sign_template_ids - sign_templates_employee_ids
        responsible = self.env.user if sign_now else self.responsible_id
        for employee in self.employee_ids:
            employee_email = email_by_employee[employee]

            for sign_template_id in sign_templates_employee_ids:
                # CASE 1: HR responsible is selected
                if self.signing_employee == 'hr_responsible':
                    partner_to_sign = responsible.partner_id.id
                    signer_email = responsible.partner_id.email_normalized
                # CASE 2: Employee is the signer
                else:
                    partner_to_sign = partner_by_employee[employee].id
                    signer_email = employee_email
                sign_values.append((
                    sign_template_id, employee,
                    [{'role_id': self.employee_role_id.id,
                    'partner_id': partner_to_sign,
                    'signer_email': signer_email}]
                ))
            for sign_template_id in sign_templates_both_ids:
                second_role = sign_template_id.sign_item_ids.responsible_id - self.employee_role_id
                sign_values.append((
                    sign_template_id, employee,
                    [{'role_id': self.employee_role_id.id,
                    'partner_id': partner_by_employee[employee].id,
                    'signer_email': employee_email},
                    {'role_id': second_role.id,
                    'partner_id': self.responsible_id.partner_id.id,
                    'signer_email': self.responsible_id.partner_id.email_normalized}]
                ))

        sign_requests = self.env['sign.request'].with_context(no_sign_mail=sign_now).create([{
            'template_id': sign_request_values[0].id,
            'request_item_ids': [Command.create({
                'partner_id': signer['partner_id'],
                'role_id': signer['role_id'],
                'signer_email': signer['signer_email'],
            }) for signer in sign_request_values[2]],
            'reference': sign_request_values[0].name,
            'subject': self.subject,
            'message': self.message,
            'validity': fields.Date.context_today(self) + relativedelta(days=sign_request_values[0].signature_request_validity),
            'attachment_ids': [(4, attachment.copy().id) for attachment in self.attachment_ids],  # Attachments may not be bound to multiple sign requests
            'reference_doc': f'hr.employee,{sign_request_values[1].id}',
        } for sign_request_values in sign_values])
        sign_requests.message_subscribe(partner_ids=self.cc_partner_ids.ids)

        if not self.browse().has_access('write'):
            sign_requests = sign_requests.sudo()

        for sign_request, sign_value in zip(sign_requests, sign_values):
            sign_request.toggle_favorited()
            employee = sign_value[1]
            if self.version_id.employee_id == employee:
                self.version_id.sign_request_ids += sign_request
            else:
                employee.sign_request_ids += sign_request

        for employee in self.employee_ids:
            if self.responsible_id and sign_templates_both_ids:
                signatories_text = self.env._(
                    "%(responsible)s, %(employee)s",
                    responsible=self.responsible_id.display_name,
                    employee=employee.display_name,
                )
            else:
                signer_name = (
                    responsible.display_name
                    if self.signing_employee == 'hr_responsible'
                    else employee.display_name
                )

                signatories_text = self.env._(
                    "%(signer)s",
                    signer=signer_name,
                )
            documents = Markup("").join(
                Markup("<li>%s</li>") % escape(name)
                for name in self.sign_template_ids.mapped('name')
            )
            body = Markup("%(request_text)s<br/><ul>%(documents)s</ul> %(signer_text)s") % {
                "request_text": self.env._("Signature requested for the following document(s):"),
                "documents": documents,
                "signer_text": self.env._("Signer(s): %(signatories)s", signatories=signatories_text),
            }
            employee.message_post(body=body)

        if not sign_now and (len(sign_requests) == 1 and ((self.env.user.id in self.employee_ids.user_id.ids) or (self.env.user.id == self.responsible_id.id and sign_templates_both_ids))):
            return sign_requests.go_to_document()
        return sign_requests

    def sign_now(self):
        """ Create the signature request and redirect to the signable document if the hr_responsible is a signer. """
        sign_requests = self.validate_signature(sign_now=True)
        # A missing email makes validate_signature return a notification action instead of the requests.
        if isinstance(sign_requests, dict):
            return sign_requests
        return sign_requests.go_to_signable_document()
