# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrContractSalaryBenefit(models.Model):
    _name = 'hr.contract.salary.benefit'
    _inherit = 'hr.contract.salary.benefit'

    def _get_binary_field_domain(self):
        return [
            ('model', '=', 'hr.version'),
            ('ttype', '=', 'binary')]

    is_configurable_benefit = fields.Boolean(string="Configurable Benefit", help="Enable this option to include this benefit in the employee’s salary configurator, allowing them to customize it.")
    show_name = fields.Boolean(string="Show Name", default=True, help='Whether the name should be displayed in the Salary Configurator')
    folded = fields.Boolean()
    fold_label = fields.Char(translate=True)
    fold_res_field_id = fields.Many2one(
        'ir.model.fields', string="Fold Condition", domain="[('id', 'in', allowed_field)]", ondelete='cascade',
        help='The field here needs to be set for this benefit to be folded by default.')
    fold_field = fields.Char(related='fold_res_field_id.name', string="Fold Field Name", readonly=True)
    manual_res_field_id = fields.Many2one(
        'ir.model.fields', string="Manual Field in Contract", domain="[('id', 'in', allowed_field)]", ondelete='cascade',
        help='Contract field used to manually encode a benefit value.')
    manual_field = fields.Char(related='manual_res_field_id.name', string="Manual Field Name", readonly=True)
    benefit_ids = fields.Many2many(
        'hr.contract.salary.benefit',
        'hr_contract_salary_benefit_rel',
        'benefit_ids',
        'mandatory_benefit_ids',
        help='Select other Benefits that need to be selected to make this Benefit available',
        string="Mandatory Benefits",
        store=True,
        readonly=False,
        domain="[('id', '!=', id), ('structure_type_id', '=', structure_type_id)]",
    )
    icon = fields.Char(compute='_compute_icon', store=True, readonly=False)
    display_type = fields.Selection(selection=[
        ('always', 'Always Selected'),
        ('dropdown', 'Dropdown'),
        ('dropdown-group', 'Dropdown Group'),
        ('radio', 'Radio Buttons'),
        ('slider', 'Slider'),
        ('manual', 'Manual Input'),
        ('text', 'Text'),
    ])
    description = fields.Html('Description', translate=True)
    slider_min = fields.Float()
    slider_max = fields.Float()
    slider_step = fields.Integer(default=1)
    value_ids = fields.One2many('hr.contract.salary.benefit.value', 'benefit_id')
    value_type = fields.Selection([('float', 'Float'), ('text', 'Text')], default='float')
    always_show_description = fields.Boolean(string="Always Show Description", help="If unchecked, Description will only be shown when Benefit is selected", default=True)
    requested_documents_field_ids = fields.Many2many('ir.model.fields', domain=_get_binary_field_domain, string="Requested Documents (IDs)")
    requested_documents_fields_string = fields.Text('Requested Documents', compute="_compute_requested_fields_string", readonly=True)
    requested_documents = fields.Char(compute='_compute_requested_documents', string="Requested Documents Fields", compute_sudo=True)

    uom = fields.Selection([
        ('days', 'Days'),
        ('percent', 'Percent'),
        ('currency', 'Currency')], string="Unit of Measure", default='currency')

    activity_type_id = fields.Many2one('mail.activity.type', string='Activity Type', help="The type of activity that will be created automatically on the contract if this benefit is chosen by the employee.")
    activity_creation = fields.Selection([
        ('running', 'Employee signs his contract'),
        ('countersigned', 'Contract is countersigned')], default='running',
        help='Choose when the activity is created:\n'
             '- Employee signs his contract: Activity is created as soon as the employee signed the contract\n'
             '- Contract is countersigned: HR responsible have signed the contract and conclude the process.')
    activity_creation_type = fields.Selection([
        ('always', 'When the benefit is set'),
        ('onchange', 'When the benefit is modified')], default='always',
        help='Define when the system creates a new activity:\n'
             '- When the benefit is set: Unique creation the first time the employee will take the benefit\n'
             '- When the benefit is modified: Activity will be created for each change regarding the benefit.')
    activity_responsible_id = fields.Many2one('res.users', 'Assigned to')
    sign_template_id = fields.Many2one('sign.template', string="Template to Sign", help="Documents selected here will be requested to the employee for additional signatures related to the benefit. eg: A company car policy to approve if you choose a company car.")
    sign_copy_partner_id = fields.Many2one('res.partner', string="Send a copy to", help="Email address to which to transfer the signature.")
    sign_frenquency = fields.Selection([
        ('onchange', 'When the benefit is set'),
        ('always', 'When the benefit is modified')], string="Sign Creation Type", default="onchange",
        help='Define when the system creates a new sign request:\n'
             '- When the benefit is set: Unique signature request the first time the employee will take the benefit\n'
             '- When the benefit is modified: Signature request will be created for each change regarding the benefit.')

    _required_fold_res_field_id = models.Constraint(
        'check (folded = FALSE OR (folded = TRUE AND fold_res_field_id IS NOT NULL))',
        "A folded field is required",
    )

    @api.depends_context('lang')
    @api.depends('requested_documents_field_ids')
    def _compute_requested_fields_string(self):
        self.requested_documents_fields_string = False
        for record in self:
            if record.requested_documents_field_ids:
                record.requested_documents_fields_string = ', '.join([f.field_description for f in record.sudo().requested_documents_field_ids])

    @api.depends('requested_documents_field_ids')
    def _compute_requested_documents(self):
        names = []
        for benefit in self:
            benefit.requested_documents = ','.join(benefit.requested_documents_field_ids.mapped('name'))
            names.extend(benefit.requested_documents_field_ids.mapped('name'))
        self._set_requested_documents_as_required(names)

    def _set_requested_documents_as_required(self, names):
        personal_infos = self.env['hr.contract.salary.personal.info'].search([('field', 'in', names)])
        if personal_infos:
            personal_infos.is_required = True

    @api.constrains('slider_min', 'slider_max')
    def _check_min_inferior_to_max(self):
        for record in self:
            if record.display_type == 'slider' and record.slider_min > record.slider_max:
                raise ValidationError(_('The minimum value for the slider should be inferior to the maximum value.'))

    @api.constrains('display_type', 'res_field_id', 'source')
    def _check_benefits_field(self):
        white_list = ['radio', 'slider', 'manual', 'always']
        for record in self:
            if record.source == 'rule' and record.display_type not in white_list:
                raise ValidationError(self.env._('The display type of a benefit linked to a salary rule must be one of the following: %s') % ', '.join(white_list))

    @api.constrains('value_ids', 'value_type')
    def _check_valid_float_values(self):
        for record in self:
            if record.value_type == 'float':
                for value_id in record.value_ids:
                    try:
                        float(value_id.value)
                    except ValueError:
                        raise ValidationError(self.env._("All benefit values must be valid floats."))

    @api.depends('show_name')
    def _compute_icon(self):
        self.filtered(lambda b: not b.show_name).icon = False


class HrContractSalaryBenefitValue(models.Model):
    _name = 'hr.contract.salary.benefit.value'
    _description = 'Contract Benefit Value'
    _order = 'sequence'

    name = fields.Char(translate=True)
    sequence = fields.Integer(default=100)
    benefit_id = fields.Many2one('hr.contract.salary.benefit', index='btree_not_null')
    value = fields.Char()
    selector_highlight = fields.Selection(selection=[('none', 'None'), ('red', 'Red')], string="Selector Highlight", default='none')
    value_type = fields.Selection(related='benefit_id.value_type')
    always_show_description = fields.Boolean()

    display_type = fields.Selection([
            ('line', 'Line'),
            ('section', 'Section'),
        ],
        default='line',
    )
    benefit_display_type = fields.Selection(related='benefit_id.display_type', string='Benefit Display Type')

    def _get_value(self):
        self.ensure_one()
        return float(self.value) if self.value_type == 'float' else self.value
