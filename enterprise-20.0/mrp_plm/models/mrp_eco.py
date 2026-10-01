# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from itertools import chain
from random import randint

import ast

from markupsafe import Markup

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command, Domain


class MrpEcoType(models.Model):
    _name = 'mrp.eco.type'
    _description = 'ECO Type'
    _inherit = ['mail.alias.mixin', 'mail.thread']

    _order = "sequence, id"

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence')
    nb_ecos = fields.Integer('ECOs', compute='_compute_nb')
    nb_approvals = fields.Integer('Waiting Approvals', compute='_compute_nb')
    nb_approvals_my = fields.Integer('Waiting my Approvals', compute='_compute_nb')
    nb_validation = fields.Integer('To Apply', compute='_compute_nb')
    color = fields.Integer('Color', default=1)
    stage_ids = fields.Many2many('mrp.eco.stage', 'mrp_eco_stage_type_rel', 'type_id', 'stage_id', string='Stages')

    def _compute_nb(self):
        # TDE FIXME: this seems not good for performances, to check (replace by _read_group later on)
        MrpEco = self.env['mrp.eco']
        for eco_type in self:
            eco_type.nb_ecos = MrpEco.search_count([
                ('type_id', 'in', eco_type.ids), ('state', '!=', 'done')
            ])
            eco_type.nb_validation = MrpEco.search_count([
                ('type_id', 'in', eco_type.ids),
                ('stage_id.allow_apply_change', '=', True),
                ('state', '=', 'progress')
            ])
            eco_type.nb_approvals = MrpEco.search_count([
                ('type_id', 'in', eco_type.ids),
                ('approval_ids.status', '=', 'none')
            ])
            approvals_waiting_for_me = self.env['mrp.eco.approval'].search_read([
                ('eco_id.type_id', 'in', eco_type.ids),
                ('eco_id.active', '=', True),
                ('status', '=', 'none'),
                ('required_user_ids', '=', self.env.user.id)
            ], fields=['eco_id'])
            num_eco = len({app_data['eco_id'] for app_data in approvals_waiting_for_me})
            eco_type.nb_approvals_my = num_eco

    def _alias_get_creation_values(self):
        values = super(MrpEcoType, self)._alias_get_creation_values()
        values['alias_model_id'] = self.env['ir.model']._get('mrp.eco').id
        if self.id:
            values['alias_defaults'] = defaults = ast.literal_eval(self.alias_defaults or "{}")
            defaults['type_id'] = self.id
        return values


class MrpEcoApprovalTemplate(models.Model):
    _name = 'mrp.eco.approval.template'
    _order = "sequence"
    _description = 'ECO Approval Template'

    name = fields.Char('Role', required=True)
    sequence = fields.Integer('Sequence')
    approval_type = fields.Selection([
        ('optional', 'Approves, but the approval is optional'),
        ('mandatory', 'Is required to approve'),
        ('comment', 'Comments only')], 'Approval Type',
        default='mandatory', required=True, index=True)
    user_ids = fields.Many2many('res.users', string='Users', domain=lambda self: [('all_group_ids', 'in', self.env.ref('mrp_plm.group_plm_user').id)], required=True)
    stage_id = fields.Many2one('mrp.eco.stage', 'Stage', required=True, index=True)

    @api.constrains('user_ids', 'stage_id')
    def _check_unique_user_stage(self):
        domain = Domain.OR([
            [('id', '!=', record.id),
            ('stage_id', '=', record.stage_id.id),
            ('user_ids', 'in', record.user_ids.ids)]
            for record in self.filtered('user_ids')
        ])
        duplicate = self.env['mrp.eco.approval.template'].search_count(domain, limit=1)
        if duplicate:
            raise ValidationError(_('A user cannot be assigned more than once to the same stage'))


class MrpEcoApproval(models.Model):
    _name = 'mrp.eco.approval'
    _description = 'ECO Approval'
    _order = 'approval_date desc'

    eco_id = fields.Many2one(
        'mrp.eco', 'ECO',
        ondelete='cascade', required=True, index=True)
    approval_template_id = fields.Many2one(
        'mrp.eco.approval.template', 'Template',
        ondelete='cascade', required=True)
    name = fields.Char('Role', related='approval_template_id.name')
    user_id = fields.Many2one(
        'res.users', 'Approved by')
    required_user_ids = fields.Many2many(
        'res.users', string='Requested Users', related='approval_template_id.user_ids', readonly=False)
    template_stage_id = fields.Many2one(
        'mrp.eco.stage', 'Approval Stage',
        related='approval_template_id.stage_id')
    eco_stage_id = fields.Many2one(
        'mrp.eco.stage', 'ECO Stage',
        related='eco_id.stage_id')
    status = fields.Selection([
        ('none', 'Not Yet'),
        ('comment', 'Commented'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')], string='Status',
        default='none', required=True, index=True)
    approval_date = fields.Datetime('Approval Date')
    is_closed = fields.Boolean()
    is_approved = fields.Boolean(
        compute='_compute_is_approved', store=True)
    is_rejected = fields.Boolean(
        compute='_compute_is_rejected', store=True)
    awaiting_my_validation = fields.Boolean(
        compute='_compute_awaiting_my_validation', search='_search_awaiting_my_validation')

    @api.depends('status', 'approval_template_id.approval_type')
    def _compute_is_approved(self):
        for rec in self:
            if rec.approval_template_id.approval_type == 'mandatory':
                rec.is_approved = rec.status == 'approved'
            else:
                rec.is_approved = True

    @api.depends('status', 'approval_template_id.approval_type')
    def _compute_is_rejected(self):
        for rec in self:
            if rec.approval_template_id.approval_type == 'mandatory':
                rec.is_rejected = rec.status == 'rejected'
            else:
                rec.is_rejected = False

    @api.depends('status', 'approval_template_id.approval_type')
    def _compute_awaiting_my_validation(self):
        # trigger the search method and return a domain where approval ids satisfying the conditions in the search method
        awaiting_validation_approval = self.search([('id', 'in', self.ids), ('awaiting_my_validation', '=', True)])
        # set awaiting_my_validation values for approvals
        awaiting_validation_approval.awaiting_my_validation = True
        (self - awaiting_validation_approval).awaiting_my_validation = False

    def _search_awaiting_my_validation(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [('required_user_ids', 'in', self.env.uid),
                ('approval_template_id.approval_type', 'in', ('mandatory', 'optional')),
                ('status', '!=', 'approved'),
                ('is_closed', '=', False)]


class MrpEcoStage(models.Model):
    _name = 'mrp.eco.stage'
    _description = 'ECO Stage'
    _order = "sequence, id"
    _fold_name = 'folded'

    @api.model
    def _get_sequence(self):
        others = self.search([('sequence', '!=', False)], order='sequence desc', limit=1)
        if others:
            return (others[0].sequence or 0) + 1
        return 1

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=_get_sequence)
    folded = fields.Boolean('Folded in kanban view')
    allow_apply_change = fields.Boolean(string='Allow to apply changes', help='Allow to apply changes from this stage.')
    final_stage = fields.Boolean(string='Final Stage', help='Once the changes are applied, the ECOs will be moved to this stage.')
    type_ids = fields.Many2many('mrp.eco.type', 'mrp_eco_stage_type_rel', 'stage_id', 'type_id', string='Types', required=True)
    approval_template_ids = fields.One2many('mrp.eco.approval.template', 'stage_id', 'Approvals')
    approval_roles = fields.Char('Approval Roles', compute='_compute_approvals', store=True)
    is_blocking = fields.Boolean('Blocking Stage', compute='_compute_is_blocking', store=True)
    legend_blocked = fields.Char(
        'Red Kanban Label', default=lambda s: s.env._('Blocked'), translate=True, required=True,
        help='Override the default value displayed for the blocked state for kanban selection, when the ECO is in that stage.')
    legend_done = fields.Char(
        'Green Kanban Label', default=lambda s: s.env._('Ready'), translate=True, required=True,
        help='Override the default value displayed for the done state for kanban selection, when the ECO is in that stage.')
    legend_normal = fields.Char(
        'Grey Kanban Label', default=lambda s: s.env._('In Progress'), translate=True, required=True,
        help='Override the default value displayed for the normal state for kanban selection, when the ECO is in that stage.')
    description = fields.Text(help="Description and tooltips of the stage states.")

    @api.depends('approval_template_ids.name')
    def _compute_approvals(self):
        for rec in self:
            rec.approval_roles = ', '.join(rec.approval_template_ids.mapped('name'))

    @api.depends('approval_template_ids.approval_type')
    def _compute_is_blocking(self):
        for rec in self:
            rec.is_blocking = any(template.approval_type == 'mandatory' for template in rec.approval_template_ids)


class MrpEco(models.Model):
    _name = 'mrp.eco'
    _description = 'Engineering Change Order (ECO)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _priority_field = 'priority'

    name = fields.Char('Reference', copy=False, required=True)
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user, tracking=True, check_company=True)
    type_id = fields.Many2one('mrp.eco.type', 'ECO Type', required=True, default=lambda self: self.env['mrp.eco.type'].search([], limit=1))
    stage_id = fields.Many2one(
        'mrp.eco.stage', 'Stage', ondelete='restrict', copy=False, domain="[('type_ids', 'in', type_id)]",
        group_expand='_read_group_stage_ids', tracking=True,
        default=lambda self: self.env['mrp.eco.stage'].search([('type_ids', 'in', self.env.context.get('default_type_id'))], limit=1))
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    tag_ids = fields.Many2many('mrp.eco.tag', string='Tags')
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'High')], string='Priority', tracking=True,
        index=True)
    note = fields.Html('Note')
    effectivity_date = fields.Datetime('Effective Date', tracking=True, help="For reference only.")
    approval_ids = fields.One2many('mrp.eco.approval', 'eco_id', 'Approvals', help='Approvals by stage')

    state = fields.Selection([
        ('confirmed', 'To Do'),
        ('progress', 'In Progress'),
        ('rebase', 'Rebase'),
        ('conflict', 'Conflict'),
        ('done', 'Done')], string='Status',
        copy=False, default='confirmed', readonly=True, required=True, index=True)
    user_can_approve = fields.Boolean(
        'Can Approve', compute='_compute_user_approval',
        help='Technical field to check if approval by current user is required')
    user_can_reject = fields.Boolean(
        'Can Reject', compute='_compute_user_approval',
        help='Technical field to check if reject by current user is possible')
    kanban_state = fields.Selection([
        ('normal', 'In Progress'),
        ('done', 'Approved'),
        ('blocked', 'Blocked')], string='Kanban State',
        copy=False, compute='_compute_kanban_state', store=True, readonly=False)
    legend_blocked = fields.Char(related='stage_id.legend_blocked', string='Kanban Blocked Explanation', related_sudo=False)
    legend_done = fields.Char(related='stage_id.legend_done', string='Kanban Valid Explanation', related_sudo=False)
    legend_normal = fields.Char(related='stage_id.legend_normal', string='Kanban Ongoing Explanation', related_sudo=False)
    kanban_state_label = fields.Char(compute='_compute_kanban_state_label', string='Kanban State Label', tracking=True)
    allow_change_kanban_state = fields.Boolean(
        'Allow Change Kanban State', compute='_compute_allow_change_kanban_state')
    allow_change_stage = fields.Boolean(
        'Allow Change Stage', compute='_compute_allow_change_stage')
    allow_apply_change = fields.Boolean(
        'Show Apply Change', compute='_compute_allow_apply_change')
    show_eco_type = fields.Boolean(
        compute='_compute_show_eco_type')

    product_tmpl_id = fields.Many2one('product.template', "Product", check_company=True, index='btree_not_null')
    production_id = fields.Many2one(
        'mrp.production', string='Manufacturing Orders', readonly=True, copy=False, index='btree_not_null')
    bom_id = fields.Many2one(
        'mrp.bom', "Bill of Materials", check_company=True)  # Should at least have bom or routing on which it is applied?
    bom_id_domain = fields.Char(compute='_compute_bom_id_domain', export_string_translation=False)
    new_bom_id = fields.Many2one(
        'mrp.bom', 'New Bill of Materials',
        copy=False, index='btree_not_null')
    new_bom_revision = fields.Integer('BoM Revision', related='new_bom_id.version', readonly=False)
    bom_change_ids = fields.One2many(
        'mrp.eco.bom.change', 'eco_id', string="ECO BoM Changes",
        compute='_compute_bom_change_ids', help='Difference between old BoM and new BoM revision', store=True)
    bom_change_ids_on_line = fields.One2many(
        'mrp.eco.bom.change', 'eco_id', string="ECO BoM Changes - Component",
        domain=[('bom_line_id', '!=', False)])
    bom_change_ids_on_byproduct = fields.One2many(
        'mrp.eco.bom.change', 'eco_id', string="ECO BoM Changes - By-Product",
        domain=[('byproduct_id', '!=', False)])
    bom_rebase_ids = fields.One2many('mrp.eco.bom.change', 'rebase_id', string="BoM Rebase")
    routing_change_ids = fields.One2many(
        'mrp.eco.routing.change', 'eco_id', string="ECO Routing Changes",
        compute='_compute_routing_change_ids', help='Difference between old operation and new operation revision', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    total_cost = fields.Monetary(compute='_compute_total_cost', currency_field='currency_id')
    used_in_count = fields.Integer('# Used In', compute='_compute_used_in_count')
    document_count = fields.Integer('# Attachments', compute='_compute_attachments')
    document_ids = fields.One2many(
        'product.document', 'res_id', string='Attachments',
        bypass_search_access=True, domain=lambda self: [('res_model', '=', self._name)])
    displayed_image_id = fields.Many2one(
        'product.document', 'Displayed Image',
        domain="[('res_model', '=', 'mrp.eco'), ('res_id', '=', id), ('mimetype', 'ilike', 'image')]")
    displayed_image_attachment_id = fields.Many2one('ir.attachment', related='displayed_image_id.ir_attachment_id', readonly=False)
    color = fields.Integer('Color')
    active = fields.Boolean('Active', default=True, help="If the active field is set to False, it will allow you to hide the engineering change order without removing it.")
    current_bom_id = fields.Many2one('mrp.bom', string="New Bom")
    previous_change_ids = fields.One2many('mrp.eco.bom.change', 'eco_rebase_id', string="Previous ECO Changes", compute='_compute_previous_bom_change', store=True)

    def _compute_attachments(self):
        for p in self:
            p.document_count = len(p.document_ids)

    def _compute_used_in_count(self):
        for eco in self:
            eco.used_in_count = len(eco._get_used_in_boms().product_tmpl_id)

    def _get_used_in_boms(self):
        self.ensure_one()
        used_in_boms = self.env['mrp.bom']
        templates_to_check = self.product_tmpl_id
        checked_templates = self.env['product.template']
        while templates_to_check:
            checked_templates |= templates_to_check
            bom_lines = self.env['mrp.bom.line'].search([
                ('bom_id.active', '=', True),
                ('product_tmpl_id', 'in', templates_to_check.ids),
            ])
            parent_boms = bom_lines.bom_id
            parent_product_templates = parent_boms.product_tmpl_id - checked_templates
            used_in_boms |= parent_boms
            templates_to_check = parent_product_templates
        return used_in_boms

    @api.depends('product_tmpl_id', 'product_tmpl_id.bom_ids', 'product_tmpl_id.bom_ids.active')
    def _compute_bom_id_domain(self):
        for eco in self:
            boms = eco.product_tmpl_id.bom_ids
            eco.bom_id_domain = [('id', 'in', boms.ids)] if boms else []

    def _compute_total_cost(self):
        for eco in self:
            total_component_cost = sum(eco.bom_change_ids_on_line.mapped('cost_computed'))
            total_operation_cost = sum(eco.routing_change_ids.mapped('cost_computed'))
            eco.total_cost = total_component_cost + total_operation_cost

    def _is_conflict(self, new_bom_lines, changes=None):
        # Find rebase lines having conflict or not.
        reb_conflicts = self.env['mrp.eco.bom.change']
        for reb_line in changes:
            new_line = new_bom_lines.get(reb_line.product_id, None)
            if new_line and (reb_line.old_operation_id, reb_line.old_uom_id, reb_line.old_product_qty) != (new_line.operation_id, new_line.uom_id, new_line.product_qty):
                reb_conflicts |= reb_line
        reb_conflicts.write({'conflict': True})
        return reb_conflicts

    def _get_difference_bom_lines(self, old_bom, new_bom):
        # Return difference lines from two bill of material.
        new_bom_commands = [Command.clear()]
        if not new_bom:
            return new_bom_commands

        old_bom_lines = defaultdict(list)
        for line in old_bom.bom_line_ids:
            old_bom_lines[line._get_sync_values()].append(line)
        for new_line in new_bom.bom_line_ids:
            # lines for a same product are matched by sequence. Magic matching with operation is not wanted nor supported
            old_lines = old_bom_lines.get(new_line._get_sync_values())
            old_line = old_lines.pop(0) if old_lines else False
            if old_line and (
                    new_line.uom_id != old_line.uom_id
                    or new_line.uom_id.compare(new_line.product_qty, old_line.product_qty)
                    or new_line.operation_id.name != old_line.operation_id.name
            ):
                new_bom_commands += [Command.create({
                    'change_type': 'update',
                    'product_id': new_line.product_id.id,
                    'old_product_qty': old_line.product_qty,
                    'new_product_qty': new_line.product_qty,
                    'old_uom_id': old_line.uom_id.id,
                    'new_uom_id': new_line.uom_id.id,
                    'old_operation_id': old_line.operation_id.id,
                    'new_operation_id': new_line.operation_id.id,
                    'bom_line_id': new_line.id,
                })]
            elif not old_line:
                new_bom_commands += [Command.create({
                    'change_type': 'add',
                    'product_id': new_line.product_id.id,
                    'new_product_qty': new_line.product_qty,
                    'new_uom_id': new_line.uom_id.id,
                    'new_operation_id': new_line.operation_id.id,
                    'bom_line_id': new_line.id,
                })]
        for old_line in chain.from_iterable(old_bom_lines.values()):
            new_bom_commands += [Command.create({
                'change_type': 'remove',
                'product_id': old_line.product_id.id,
                'old_product_qty': old_line.product_qty,
                'old_uom_id': old_line.uom_id.id,
                'old_operation_id': old_line.operation_id.id,
                'bom_line_id': old_line.id,
            })]

        old_byproducts = defaultdict(list)
        for byproduct in old_bom.byproduct_ids:
            old_byproducts[byproduct._get_sync_values()].append(byproduct)
        for new_byproduct in new_bom.byproduct_ids:
            old_byproducts_list = old_byproducts.get(new_byproduct._get_sync_values())
            old_byproduct = old_byproducts_list.pop(0) if old_byproducts_list else False
            if old_byproduct and (
                    new_byproduct.uom_id != old_byproduct.uom_id
                    or new_byproduct.uom_id.compare(new_byproduct.product_qty, old_byproduct.product_qty)
                    or new_byproduct.operation_id.name != old_byproduct.operation_id.name
            ):
                new_bom_commands += [Command.create({
                    'change_type': 'update',
                    'product_id': new_byproduct.product_id.id,
                    'old_product_qty': old_byproduct.product_qty,
                    'new_product_qty': new_byproduct.product_qty,
                    'old_uom_id': old_byproduct.uom_id.id,
                    'new_uom_id': new_byproduct.uom_id.id,
                    'old_operation_id': old_byproduct.operation_id.id,
                    'new_operation_id': new_byproduct.operation_id.id,
                    'byproduct_id': new_byproduct.id
                })]
            elif not old_byproduct:
                new_bom_commands += [Command.create({
                    'change_type': 'add',
                    'product_id': new_byproduct.product_id.id,
                    'new_product_qty': new_byproduct.product_qty,
                    'new_uom_id': new_byproduct.uom_id.id,
                    'new_operation_id': new_byproduct.operation_id.id,
                    'byproduct_id': new_byproduct.id,
                })]
        for old_byproduct in chain.from_iterable(old_byproducts.values()):
            new_bom_commands += [Command.create({
                'change_type': 'remove',
                'product_id': old_byproduct.product_id.id,
                'old_product_qty': old_byproduct.product_qty,
                'old_uom_id': old_byproduct.uom_id.id,
                'old_operation_id': old_byproduct.operation_id.id,
                'byproduct_id': old_byproduct.id,
            })]

        return new_bom_commands

    def rebase(self, old_bom_lines, new_bom_lines, rebase_lines):
        """
        This method will apply changes in new revision of BoM
            old_bom_lines : Previous BoM or Old BoM version lines.
            new_bom_lines : New BoM version lines.
            rebase_lines  : Changes done in previous version
        """
        for reb_line in rebase_lines:
            new_bom_line = new_bom_lines.get(reb_line.product_id, None)
            if new_bom_line:
                if new_bom_line.product_qty + reb_line.upd_product_qty > 0.0:
                    # Update line if it exist in new bom.
                    new_bom_line.write({
                        'product_qty': new_bom_line.product_qty + reb_line.upd_product_qty,
                        'uom_id': reb_line.new_uom_id.id,
                        'operation_id': reb_line.new_operation_id.id,
                    })
                else:
                    # Unlink lines if old bom removed lines
                    new_bom_line.unlink()
            else:
                # Add bom line in new bom for rebase.
                old_line = old_bom_lines.get(reb_line.product_id, None)
                if old_line:
                    old_line.copy({'bom_id': self.new_bom_id.id})
        return True

    def apply_rebase(self):
        """ Apply rebase changes in new version of BoM """
        self.ensure_one()
        # Rebase logic applied..
        vals = {'state': 'progress'}
        if self.bom_rebase_ids:
            new_bom_lines = {line.product_id: line for line in self.new_bom_id.bom_line_ids}
            if self._is_conflict(new_bom_lines, self.bom_rebase_ids):
                return self.write({'state': 'conflict'})
            else:
                old_bom_lines = {line.product_id: line for line in self.bom_id.bom_line_ids}
                self.rebase(old_bom_lines, new_bom_lines, self.bom_rebase_ids)
                # Remove all rebase line of current eco.
                self.bom_rebase_ids.unlink()
        if self.previous_change_ids:
            new_bom_lines = {line.product_id: line for line in self.new_bom_id.bom_line_ids}
            if self._is_conflict(new_bom_lines, self.previous_change_ids):
                return self.write({'state': 'conflict'})
            else:
                new_activated_bom_lines = {line.product_id: line for line in self.current_bom_id.bom_line_ids}
                self.rebase(new_activated_bom_lines, new_bom_lines, self.previous_change_ids)
                # Remove all rebase line of current eco.
                self.previous_change_ids.unlink()
        if self.current_bom_id:
            self.new_bom_id.write({'version': self.current_bom_id.version, 'previous_bom_id': self.current_bom_id.id})
            vals.update({'bom_id': self.current_bom_id.id, 'current_bom_id': False})
        self.message_post(body=_('Successfully Rebased!'))
        return self.write(vals)

    @api.depends('bom_id.bom_line_ids',
                 'new_bom_id.bom_line_ids', 'new_bom_id.bom_line_ids.product_qty', 'new_bom_id.bom_line_ids.uom_id', 'new_bom_id.bom_line_ids.operation_id', 'new_bom_id.bom_line_ids.product_id',
                 'bom_id.byproduct_ids',
                 'new_bom_id.byproduct_ids', 'new_bom_id.byproduct_ids.product_qty', 'new_bom_id.byproduct_ids.operation_id', 'new_bom_id.byproduct_ids.product_id', 'new_bom_id.byproduct_ids.uom_id')
    def _compute_bom_change_ids(self):
        # Compute difference between old bom and new bom revision.
        for eco in self:
            eco.bom_change_ids = eco._get_difference_bom_lines(eco.bom_id, eco.new_bom_id)

    @api.depends('bom_id.bom_line_ids', 'current_bom_id.bom_line_ids', 'current_bom_id.bom_line_ids.product_qty', 'current_bom_id.bom_line_ids.uom_id', 'current_bom_id.bom_line_ids.operation_id')
    def _compute_previous_bom_change(self):
        for eco in self:
            if eco.current_bom_id:
                # Compute difference between old bom and newly activated bom.
                eco.previous_change_ids = eco._get_difference_bom_lines(eco.bom_id, eco.current_bom_id)
            else:
                eco.previous_change_ids = False

    @api.depends('bom_id.operation_ids', 'bom_id.operation_ids.active', 'bom_id.operation_ids.time_mode', 'bom_id.operation_ids.time_mode_batch', 'bom_id.operation_ids.time_cycle_manual',
                 'new_bom_id.operation_ids', 'new_bom_id.operation_ids.active', 'new_bom_id.operation_ids.time_mode', 'new_bom_id.operation_ids.time_mode_batch', 'new_bom_id.operation_ids.time_cycle_manual')
    def _compute_routing_change_ids(self):
        for rec in self:
            if rec.state == 'confirmed' or not rec.new_bom_id:
                continue
            new_routing_commands = [Command.clear()]
            old_routing_lines = defaultdict(lambda: self.env['mrp.routing.workcenter'])
            # Two operations could have the same values so we save them with the same key
            for op in rec.bom_id.operation_ids:
                old_routing_lines[op._get_sync_values()] |= op
            if rec.new_bom_id and rec.bom_id:
                for operation in rec.new_bom_id.operation_ids:
                    key = (operation._get_sync_values())
                    old_op = old_routing_lines[key][:1]
                    if old_op:
                        old_routing_lines[key] -= old_op
                        if old_op.time_mode != operation.time_mode or \
                                old_op.time_mode_batch != operation.time_mode_batch or \
                                tools.float_compare(old_op.time_cycle_manual, operation.time_cycle_manual, 2) != 0 or \
                                old_op.workcenter_id != operation.workcenter_id:
                            new_routing_commands += [Command.create({
                                'change_type': 'update',
                                'workcenter_id': operation.workcenter_id.id,
                                'upd_time_mode': old_op.time_mode + ' -> ' + operation.time_mode if operation.time_mode != old_op.time_mode else '',
                                'upd_time_mode_batch': operation.time_mode_batch - old_op.time_mode_batch if operation.time_mode == 'auto' else 0,
                                'upd_time_cycle_manual': operation.time_cycle_manual - old_op.time_cycle_manual if operation.time_mode == 'manual' else 0,
                                'operation_id': operation.id,
                                'old_operation_id': old_op.id,
                            })]
                        new_routing_commands += self._prepare_detailed_change_commands(operation, old_op)
                    else:
                        new_routing_commands += [Command.create({
                            'change_type': 'add',
                            'workcenter_id': operation.workcenter_id.id,
                            'upd_time_mode': operation.time_mode,
                            'upd_time_mode_batch': operation.time_mode_batch,
                            'upd_time_cycle_manual': operation.time_cycle_manual,
                            'operation_id': operation.id,
                        })]
                        new_routing_commands += self._prepare_detailed_change_commands(operation, None)
            for old_ops in old_routing_lines.values():
                for old_op in old_ops:
                    new_routing_commands += [Command.create({
                        'change_type': 'remove',
                        'workcenter_id': old_op.workcenter_id.id,
                        'operation_id': old_op.id,
                    })]
            rec.routing_change_ids = new_routing_commands

    def _prepare_detailed_change_commands(self, new, old):
        """Necessary for overrides to track change of quality checks"""
        return []

    def _compute_user_approval(self):
        for eco in self:
            is_required_approval = eco.stage_id.approval_template_ids.filtered(lambda x: x.approval_type in ('mandatory', 'optional') and self.env.user in x.user_ids)
            user_approvals = eco.approval_ids.filtered(lambda x: x.template_stage_id == eco.stage_id and x.user_id == self.env.user and not x.is_closed)
            last_approval = user_approvals.sorted(lambda a : a.create_date, reverse=True)[:1]
            eco.user_can_approve = is_required_approval and not last_approval.is_approved
            eco.user_can_reject = is_required_approval and not last_approval.is_rejected

    @api.depends('stage_id', 'approval_ids.is_approved', 'approval_ids.is_rejected')
    def _compute_kanban_state(self):
        """ State of ECO is based on the state of approvals for the current stage. """
        for rec in self:
            approvals = rec.approval_ids.filtered(lambda app:
                app.template_stage_id == rec.stage_id and not app.is_closed)
            if not approvals:
                rec.kanban_state = 'normal'
            elif all(approval.is_approved for approval in approvals):
                rec.kanban_state = 'done'
            elif any(approval.is_rejected for approval in approvals):
                rec.kanban_state = 'blocked'
            else:
                rec.kanban_state = 'normal'

    @api.depends('kanban_state', 'stage_id', 'approval_ids')
    def _compute_allow_change_stage(self):
        for rec in self:
            approvals = rec.approval_ids.filtered(lambda app: app.template_stage_id == rec.stage_id)
            if approvals:
                rec.allow_change_stage = rec.kanban_state == 'done'
            else:
                rec.allow_change_stage = rec.kanban_state in ['normal', 'done']

    @api.depends('state', 'stage_id.allow_apply_change')
    def _compute_allow_apply_change(self):
        for rec in self:
            rec.allow_apply_change = rec.stage_id.allow_apply_change and rec.state in ('confirmed', 'progress')

    def _compute_show_eco_type(self):
        show_eco_type = self.env['mrp.eco.type'].search_count([], limit=2) > 1
        for rec in self:
            rec.show_eco_type = show_eco_type

    @api.depends('stage_id.approval_template_ids')
    def _compute_allow_change_kanban_state(self):
        for rec in self:
            rec.allow_change_kanban_state = not rec.stage_id.approval_template_ids

    @api.depends('stage_id', 'kanban_state')
    def _compute_kanban_state_label(self):
        for eco in self:
            if eco.kanban_state == 'normal':
                eco.kanban_state_label = eco.legend_normal
            elif eco.kanban_state == 'blocked':
                eco.kanban_state_label = eco.legend_blocked
            else:
                eco.kanban_state_label = eco.legend_done

    @api.onchange('product_tmpl_id')
    def onchange_product_tmpl_id(self):
        if self.product_tmpl_id.bom_ids and not self.bom_id:
            self.bom_id = self.product_tmpl_id.bom_ids.ids[0]

    @api.onchange('bom_id')
    def onchange_bom_id(self):
        if self.bom_id and not self.product_tmpl_id:
            self.product_tmpl_id = self.bom_id.product_tmpl_id

    @api.onchange('type_id')
    def onchange_type_id(self):
        self.stage_id = self.env['mrp.eco.stage'].search([('type_ids', 'in', self.type_id.id)], limit=1).id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prefix = self.env['ir.sequence'].next_by_code('mrp.eco') or ''
            name = vals['name'].strip() if vals.get('name') else ''
            vals['name'] = prefix + (f": {name}" if name else '')
        ecos = super().create(vals_list)
        ecos._create_approvals()
        return ecos

    def write(self, vals):
        if 'name' in vals and not vals['name']:
            del vals['name']
        if vals.get('stage_id'):
            newstage = self.env['mrp.eco.stage'].browse(vals['stage_id'])
            # raise exception only if we increase the stage, not on decrease
            for eco in self:
                if eco.stage_id and ((newstage.sequence, newstage.id) > (eco.stage_id.sequence, eco.stage_id.id)):
                    if not eco.allow_change_stage:
                        raise UserError(_('You cannot change the stage, as approvals are still required.'))
                    has_blocking_stages = self.env['mrp.eco.stage'].search_count([
                        ('sequence', '>=', eco.stage_id.sequence),
                        ('sequence', '<=', newstage.sequence),
                        ('type_ids', 'in', eco.type_id.id),
                        ('id', 'not in', [eco.stage_id.id] + [vals['stage_id']]),
                        ('is_blocking', '=', True)])
                    if has_blocking_stages:
                        raise UserError(_('You cannot change the stage, as approvals are required in the process.'))
                if eco.stage_id != newstage:
                    eco.approval_ids.filtered(lambda x: x.status != 'none').write({'is_closed': True})
                    eco.approval_ids.filtered(lambda x: x.status == 'none').unlink()
        if 'displayed_image_attachment_id' in vals:
            doc = False
            if vals['displayed_image_attachment_id']:
                doc = self.env['product.document'].search([('ir_attachment_id', '=', vals['displayed_image_attachment_id'])])
                if not doc:
                    doc = self.env['product.document'].create([{'ir_attachment_id': vals['displayed_image_attachment_id']}])
            vals.pop('displayed_image_attachment_id')
            vals['displayed_image_id'] = doc
        res = super(MrpEco, self).write(vals)
        if vals.get('stage_id'):
            self._create_approvals()
        return res

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """ Read group customization in order to display all the stages of the ECO type
        in the Kanban view, even if there is no ECO in that stage
        """
        search_domain = []
        if self.env.context.get('default_type_ids'):
            search_domain = [('type_ids', 'in', self.env.context['default_type_ids'])]

        stage_ids = stages.sudo()._search(search_domain, order=stages._order)
        return stages.browse(stage_ids)

    def message_post(self, **kwargs):
        message = super(MrpEco, self).message_post(**kwargs)
        if message.message_type == 'comment' and message.author_id == self.env.user.partner_id:  # should use message_values to avoid a read
            for eco in self:
                for approval in eco.approval_ids.filtered(lambda app: app.template_stage_id == eco.stage_id and app.status == 'none' and app.approval_template_id.approval_type == 'comment'):
                    if self.env.user in approval.approval_template_id.user_ids:
                        approval.write({
                            'status': 'comment',
                            'user_id': self.env.uid
                        })
        return message

    def _create_approvals(self):
        approval_vals = []
        activity_vals = []
        for eco in self:
            for approval_template in eco.stage_id.approval_template_ids:
                approval = eco.approval_ids.filtered(lambda app: app.approval_template_id == approval_template and not app.is_closed)
                if not approval:
                    approval_vals.append({
                        'eco_id': eco.id,
                        'approval_template_id': approval_template.id,
                    })
                    for user in approval_template.user_ids:
                        # TDE TODO: link to eco approval record ?
                        activity_vals.append({
                            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                            'summary': _('ECO Approval'),
                            'user_id': user.id,
                            'res_id': eco.id,
                            'res_model_id': self.env.ref('mrp_plm.model_mrp_eco').id,
                        })
        self.env['mrp.eco.approval'].create(approval_vals)
        self.env['mail.activity'].create(activity_vals)

    def _create_or_update_approval(self, status):
        for eco in self:
            for approval_template in eco.stage_id.approval_template_ids.filtered(lambda a: self.env.user in a.user_ids):
                approvals = eco.approval_ids.filtered(lambda x: x.approval_template_id == approval_template and not x.is_closed)
                none_approvals = approvals.filtered(lambda a: a.status =='none')
                confirmed_approvals = approvals - none_approvals
                if none_approvals:
                    none_approvals.write({'status': status, 'user_id': self.env.uid, 'approval_date': fields.Datetime.now()})
                    confirmed_approvals.write({'is_closed': True})
                    approval = none_approvals[:1]
                else:
                    approvals.write({'is_closed': True})
                    approval = self.env['mrp.eco.approval'].create({
                        'eco_id': eco.id,
                        'approval_template_id': approval_template.id,
                        'status': status,
                        'user_id': self.env.uid,
                        'approval_date': fields.Datetime.now(),
                    })

                message = _("%(approval_name)s %(approver_name)s %(approval_status)s this ECO",
                    approval_name=approval.name,
                    approver_name=approval.user_id.name,
                    approval_status=approval.status,
                )
                eco.message_post(body=message, subtype_xmlid='mail.mt_comment')

    def approve(self):
        self._create_or_update_approval(status='approved')

    def reject(self):
        self._create_or_update_approval(status='rejected')

    def conflict_resolve(self):
        self.ensure_one()
        vals = {'state': 'progress'}
        if self.current_bom_id:
            vals.update({'bom_id': self.current_bom_id.id, 'current_bom_id': False})
        self.write(vals)
        # Set previous BoM on new revision and change version of BoM.
        self.new_bom_id.write({
            'version': self.bom_id.version,
            'previous_bom_id': self.bom_id.id
            })
        # Remove all rebase lines.
        rebase_lines = self.bom_rebase_ids + self.previous_change_ids
        rebase_lines.unlink()
        return True

    def _prepare_new_bom_copy_values(self):
        self.ensure_one()
        values = {
            'version': self.bom_id.version,
            'active': False,
            'previous_bom_id': self.bom_id.id,
        }
        if self.product_tmpl_id and self.bom_id.product_tmpl_id != self.product_tmpl_id:
            values['product_tmpl_id'] = self.product_tmpl_id.id
            if self.bom_id.product_id:
                values['product_id'] = self.product_tmpl_id.product_variant_id.id
        return values

    def _ensure_new_bom(self):
        self.ensure_one()
        if self.new_bom_id or not self.bom_id:
            return
        if self.production_id:
            # This ECO was generated from a MO. Uses its MO as base for the revision.
            self.new_bom_id = self.production_id._create_revision_bom()
        else:
            self.new_bom_id = self.bom_id.sudo().copy(default=self._prepare_new_bom_copy_values())

    def action_new_revision(self):
        for eco in self:
            if not eco.product_tmpl_id:
                raise UserError(_('You need to select a product before starting the revision.'))
            eco._ensure_new_bom()
            product_ids = eco.product_tmpl_id.product_variant_ids.ids
            docs = self.env['product.document'].search([
                '|',
                '&',
                ('res_model', '=', 'product.template'),
                ('res_id', '=', eco.product_tmpl_id.id),
                '&',
                ('res_model', '=', 'product.product'),
                ('res_id', 'in', product_ids),
            ])
            docs_vals = docs.copy_data({
                'res_model': 'mrp.eco',
                'res_id': eco.id,
            })
            for doc, vals in zip(docs, docs_vals):
                vals['origin_attachment_id'] = doc.ir_attachment_id.id
            self.env['product.document'].create(docs_vals)
        self.write({'state': 'progress'})

    def _set_cost(self):
        """Snapshot costs on change records so the report stays stable after validation."""
        for eco in self:
            for change in eco.bom_change_ids:
                change.cost = change.cost_computed
            for change in eco.routing_change_ids:
                change.cost = change.cost_computed

    def _log_version_update(self, types_updated):
        self.ensure_one()
        messages = [
            _('%s updated to new version.', _(' and ').join(type_updated))
            for type_updated in types_updated
            if type_updated
        ]
        body = Markup('<p><b>%s</b></p>') % Markup('<br/>').join(
            Markup('%s') % message
            for message in messages
        )
        self.message_post(body=body)

    def action_apply(self):
        self._check_company()
        eco_need_action = self.env['mrp.eco']
        for eco in self:
            if eco.state == 'done':
                continue
            if eco.state == 'rebase':
                eco.apply_rebase()
            if eco.allow_apply_change:
                if eco.new_bom_id:
                    eco.new_bom_id.apply_new_version()

                for attach in eco.with_context(active_test=False).document_ids:
                    origin = attach.origin_attachment_id
                    if not attach.active:
                        origin.unlink()
                        continue
                    if origin._compute_checksum(origin.raw) == origin._compute_checksum(attach.raw):
                        if attach.origin_attachment_id.name != attach.name:
                            attach.origin_attachment_id.name = attach.name
                        if attach.origin_attachment_id.company_id != attach.company_id:
                            attach.origin_attachment_id.company_id = attach.company_id
                        continue
                    attach.copy({
                        'res_model': 'product.template',
                        'res_id': eco.product_tmpl_id.id,
                        'origin_attachment_id': attach.ir_attachment_id.id,
                    })

                eco._set_cost()
                vals = {'state': 'done'}
                stage_id = eco.env['mrp.eco.stage'].search([
                    ('final_stage', '=', True),
                    ('type_ids', 'in', eco.type_id.id)], limit=1).id
                if stage_id:
                    vals['stage_id'] = stage_id
                eco.write(vals)
            else:
                eco_need_action |= eco
        if eco_need_action:
            return {
                'name': _('Eco'),
                'type': 'ir.actions.act_window',
                'view_mode': 'list, form',
                'views': [[False, 'list'], [False, 'form']],
                'res_model': 'mrp.eco',
                'target': 'current',
                'domain': [('id', 'in', eco_need_action.ids)],
                'context': {'search_default_changetoapply': False},
            }

    def open_wizard(self):
        self.ensure_one()
        Wizard = self.env['mrp.eco.update.product.version']
        used_in_boms = self._get_used_in_boms()
        used_in_products = used_in_boms.product_tmpl_id
        bom = self.new_bom_id
        wizard = Wizard.create({
            'eco_id': self.id,
            'product_tmpl_id': self.product_tmpl_id.id,
            'bom_id': bom.id,
            'used_in_product_tmpl_ids': [Command.set(used_in_products.ids)],
            'used_in_bom_ids': [Command.set(used_in_boms.ids)],
        })
        return {
            'name': _('Update Versions'),
            'type': 'ir.actions.act_window',
            'res_model': Wizard._name,
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_see_attachments(self):
        self.ensure_one()
        attachment_view = self.env.ref('mrp_plm.view_document_file_kanban_mrp_plm')
        context = {
            'default_res_model': self._name,
            'default_res_id': self.id,
            'default_company_id': self.company_id.id,
            'search_default_all': 1,
            'hide_upload_button': self.state == 'done',
            'create': self.state != 'done',
            'edit': self.state != 'done',
            'delete': self.state != 'done',
        }

        return {
            'name': _('Attachments'),
            'domain': ['&', ('res_model', '=', self._name), ('res_id', '=', self.id)],
            'res_model': 'product.document',
            'type': 'ir.actions.act_window',
            'view_id': attachment_view.id,
            'views': [(attachment_view.id, 'kanban'), (False, 'form')],
            'view_mode': 'kanban,list,form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Upload files to your ECO, that will be applied to the product later
                    </p><p>
                        Use this feature to store any files, like drawings or specifications.
                    </p>'''),
            'limit': 80,
            'context': context,
        }

    def action_open_production(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.action_mrp_production_form')
        action["res_id"] = self.production_id.id
        return action

    def action_open_used_in_products(self):
        self.ensure_one()
        records = self._get_used_in_boms().product_tmpl_id
        action = self.env['ir.actions.act_window']._for_xml_id('product.product_template_action_all')
        action['name'] = self.env._('Used In')
        action['domain'] = [('id', 'in', records.ids)]
        action['context'] = {}
        action['view_mode'] = 'list,form'
        action['views'] = [(self.env.ref('mrp_plm.product_template_used_in_list_view').id, 'list'), (False, 'form')]
        return action

    def action_compare_boms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('BoM Lines'),
            'res_model': 'mrp.bom.line',
            'views': [
                (self.env.ref('mrp.mrp_bom_line_view_pivot').id, 'pivot'),
            ],
            'domain': [('bom_id', 'in', (self.bom_id | self.new_bom_id).ids)],
        }

    def open_new_bom(self):
        self.ensure_one()
        return {
            'name': _('Eco BoM'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.bom',
            'target': 'current',
            'res_id': self.new_bom_id.id,
            'context': {
                'default_product_tmpl_id': self.product_tmpl_id.id,
                'default_product_id': self.product_tmpl_id.product_variant_id.id,
                'create': self.state != 'done',
                'edit': self.state != 'done',
                'delete': self.state != 'done',
            },
        }


class MrpEcoBomChange(models.Model):
    _name = 'mrp.eco.bom.change'
    _description = 'ECO BoM changes'

    eco_id = fields.Many2one('mrp.eco', 'Engineering Change', index=True, ondelete='cascade')
    company_id = fields.Many2one(related='eco_id.company_id')
    eco_rebase_id = fields.Many2one('mrp.eco', 'ECO Rebase', index='btree_not_null', ondelete='cascade')
    rebase_id = fields.Many2one('mrp.eco', 'Rebase', ondelete='cascade', index='btree_not_null')
    change_type = fields.Selection([('add', 'Add'), ('remove', 'Remove'), ('update', 'Update')], string='Type', required=True)
    product_id = fields.Many2one('product.product', 'Product', required=True)
    old_uom_id = fields.Many2one('uom.uom', 'Previous Product UoM')
    new_uom_id = fields.Many2one('uom.uom', 'New Product UoM')
    old_product_qty = fields.Float('Previous revision quantity', default=0)
    new_product_qty = fields.Float('New revision quantity', default=0)
    old_operation_id = fields.Many2one('mrp.routing.workcenter', 'Previous Consumed in Operation')
    new_operation_id = fields.Many2one('mrp.routing.workcenter', 'New Consumed in Operation')
    upd_product_qty = fields.Float('Quantity', compute='_compute_upd_product_qty', store=True, digits='Product Unit')
    cost = fields.Monetary(currency_field='currency_id')
    cost_computed = fields.Monetary(compute='_compute_cost', currency_field='currency_id')
    description = fields.Text('Description', compute='_compute_description', compute_sudo=True)
    currency_id = fields.Many2one(related='eco_id.company_id.currency_id')
    conflict = fields.Boolean()
    bom_line_id = fields.Many2one('mrp.bom.line', 'BoM Line', check_company=True)
    byproduct_id = fields.Many2one('mrp.bom.byproduct', 'BoM By-Product', check_company=True)

    def _compute_cost(self):
        for line_change in self:
            if line_change.eco_id.state == 'done':
                line_change.cost_computed = line_change.cost
                continue

            product = line_change.product_id.with_company(line_change.eco_id.company_id or self.env.company)
            new_qty = line_change.new_uom_id._compute_quantity(line_change.new_product_qty, product.uom_id) if line_change.new_uom_id else 0
            old_qty = line_change.old_uom_id._compute_quantity(line_change.old_product_qty, product.uom_id) if line_change.old_uom_id else 0
            line_change.cost_computed = (new_qty - old_qty) * product.standard_price

    @api.depends('new_product_qty', 'old_product_qty')
    def _compute_upd_product_qty(self):
        for rec in self:
            rec.upd_product_qty = rec.new_product_qty - rec.old_product_qty

    @api.depends('change_type', 'old_operation_id', 'new_operation_id', 'old_uom_id', 'new_uom_id')
    def _compute_description(self):
        self.description = False
        for rec in self:
            parts = []
            if rec.change_type != 'update':
                continue

            # Operation change
            if rec.old_operation_id.name != rec.new_operation_id.name:
                if rec.byproduct_id:
                    parts.append(self.env._(
                        "Produced in Operation: %(old)s -> %(new)s",
                        old=rec.old_operation_id.name or '',
                        new=rec.new_operation_id.name or '',
                    ))
                else:
                    parts.append(self.env._(
                        "Consumed in Operation: %(old)s -> %(new)s",
                        old=rec.old_operation_id.name or '',
                        new=rec.new_operation_id.name or '',
                    ))

            # UoM change
            if (rec.old_uom_id and rec.new_uom_id) and rec.old_uom_id != rec.new_uom_id:
                parts.append(self.env._(
                    "Unit: %(old)s -> %(new)s",
                    old=rec.old_uom_id.name,
                    new=rec.new_uom_id.name,
                ))
            rec.description = '\n'.join(parts) if parts else False


class MrpEcoRoutingChange(models.Model):
    _name = 'mrp.eco.routing.change'
    _description = 'Eco Routing changes'

    eco_id = fields.Many2one('mrp.eco', 'Engineering Change', ondelete='cascade', required=True, index=True)
    change_type = fields.Selection([('add', 'Add'), ('remove', 'Remove'), ('update', 'Update')], string='Type', required=True)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    upd_time_mode = fields.Char('Mode Change')
    upd_time_mode_batch = fields.Integer('Batch count Change')
    upd_time_cycle_manual = fields.Float('Manual Duration Change')
    description = fields.Text('Description', compute='_compute_description')
    description_reference = fields.Reference(
        string='Reference', selection=[],
        compute='_compute_description_reference')
    cost = fields.Monetary(currency_field='currency_id')
    cost_computed = fields.Monetary(compute='_compute_cost', currency_field='currency_id')
    currency_id = fields.Many2one(related='eco_id.company_id.currency_id')

    operation_id = fields.Many2one('mrp.routing.workcenter', 'Operation Id', ondelete='cascade')
    old_operation_id = fields.Many2one('mrp.routing.workcenter', 'Previous Operation')
    operation_name = fields.Char(related='operation_id.name', string='Operation')

    def _compute_cost(self):
        for op_change in self:
            if op_change.eco_id.state == 'done':
                op_change.cost_computed = op_change.cost
                continue

            if op_change.change_type == 'add':
                cost = op_change.operation_id.cost
            elif op_change.change_type == 'remove':
                cost = -op_change.operation_id.cost
            else:
                cost = op_change.operation_id.cost - op_change.old_operation_id.cost
            op_change.cost_computed = cost

    @api.depends('change_type', 'upd_time_mode', 'upd_time_mode_batch', 'upd_time_cycle_manual')
    def _compute_description(self):
        self.description = False
        for op_change in self:
            parts = []
            if op_change.change_type != 'update':
                continue
            if op_change.old_operation_id.workcenter_id != op_change.operation_id.workcenter_id:
                parts.append(self.env._(
                    "Work center: %(old)s -> %(new)s",
                    old=op_change.old_operation_id.workcenter_id.name or '',
                    new=op_change.operation_id.workcenter_id.name or '',
                ))
            if op_change.upd_time_mode:
                parts.append(self.env._(
                    "Mode: %(mode)s",
                    mode=op_change.upd_time_mode,
                ))
            if op_change.upd_time_mode_batch:
                parts.append(self.env._(
                    "Batch Count: %(count)s",
                    count=f"{op_change.upd_time_mode_batch:+d}",
                ))
            op_change.description = '\n'.join(parts) if parts else False

    def _compute_description_reference(self):
        for op_change in self:
            op_change.description_reference = False


class MrpEcoTag(models.Model):
    _name = 'mrp.eco.tag'
    _description = "ECO Tags"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char('Tag Name', required=True)
    color = fields.Integer('Color Index', default=_get_default_color)

    _name_uniq = models.Constraint(
        'unique (name)',
        "Tag name already exists!",
    )
