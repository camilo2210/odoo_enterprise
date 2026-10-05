# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    state = fields.Selection(
        selection_add=[
            ('documents_account_record_create', 'New Journal Entry'),
        ],
        ondelete={
            'documents_account_record_create': 'cascade',
        }
    )
    documents_account_create_model = fields.Selection([
        ('account.move.in_invoice', 'Vendor Bill'),
        ('account.move.out_invoice', 'Customer Invoice'),
        ('account.move.in_refund', 'Vendor Refund'),
        ('account.move.out_refund', 'Credit Note'),
        ('account.move.entry', 'Miscellaneous Operations'),
        ('account.bank.statement', 'Bank Statement'),
        ('account.move.in_receipt', 'Purchase Receipt'),
    ])
    documents_account_journal_id = fields.Many2one(
        comodel_name='account.journal',
        domain="['|', ('id', 'in', documents_account_suitable_journal_ids), ('id', '=', False)]",
        compute="_compute_documents_account_journal_id", store=True, readonly=False,
    )
    documents_account_suitable_journal_ids = fields.Many2many(
        'account.journal', compute='_compute_documents_account_suitable_journal_ids')
    documents_account_move_type = fields.Char(compute='_compute_documents_account_move_type')

    documents_folder_id = fields.Many2one(
        'documents.document',
        string='Move to Folder',
        domain="[('type', '=', 'folder'), ('shortcut_document_id', '=', False)]",
        compute='_compute_documents_folder_id',
        inverse='_inverse_documents_folder_id',
    )
    documents_add_tag_ids = fields.Many2many(
        'documents.tag',
        string='Add Tags',
        compute='_compute_documents_add_tag_ids',
        inverse='_inverse_documents_add_tag_ids',
        domain="[('id', 'not in', documents_remove_tag_ids)]",
    )
    documents_remove_tag_ids = fields.Many2many(
        'documents.tag',
        string='Remove Tags',
        compute='_compute_documents_remove_tag_ids',
        inverse='_inverse_documents_remove_tag_ids',
        domain="[('id', 'not in', documents_add_tag_ids)]",
    )

    @api.depends('state', 'child_ids.state', 'child_ids.model_id', 'child_ids.update_path', 'child_ids.resource_ref')
    def _compute_documents_folder_id(self):
        account_actions = self.filtered(lambda a: a.state == "documents_account_record_create")
        (self - account_actions).documents_folder_id = False
        for action in account_actions:
            move_action = action._document_get_move_action()
            action.documents_folder_id = move_action.resource_ref

    def _inverse_documents_folder_id(self):
        to_create = []
        to_unlink = self.env['ir.actions.server']
        for action in self:
            move_action = action._document_get_move_action()
            if action.documents_folder_id and move_action:
                move_action.resource_ref = action.documents_folder_id
            elif action.documents_folder_id and not move_action:
                to_create.append({
                    'name': _('Move to %s', action.documents_folder_id.name),
                    'model_id': self.env['ir.model']._get_id('documents.document'),
                    'state': 'object_write',
                    'update_path': 'folder_id',
                    'resource_ref': f'documents.document,{action.documents_folder_id.id}',
                    'parent_id': action.id,
                    'usage': 'ir_actions_server',
                })
            elif move_action:
                to_unlink |= move_action
        self.create(to_create)
        to_unlink.unlink()

    def _document_get_move_action(self):
        self.ensure_one()
        return self.child_ids.filtered(lambda a:
            a.model_id.id == self.env['ir.model']._get_id('documents.document')
            and a.state == 'object_write'
            and a.update_path == 'folder_id'
        )[:1]

    @api.depends('state', 'child_ids.state', 'child_ids.model_id', 'child_ids.update_path',
                 'child_ids.update_m2m_operation', 'child_ids.resource_ref')
    def _compute_documents_add_tag_ids(self):
        account_actions = self.filtered(lambda a: a.state == "documents_account_record_create")
        (self - account_actions).documents_add_tag_ids = False
        for action in account_actions:
            tag_actions = action._document_get_tag_actions('add')
            action.documents_add_tag_ids = [a.resource_ref.id for a in tag_actions]

    def _inverse_documents_add_tag_ids(self):
        vals_list = []
        to_unlink = self.env['ir.actions.server']
        for action in self:
            vals, unlink_ids = action._document_set_tag_actions('add', action.documents_add_tag_ids)
            vals_list += vals
            to_unlink |= unlink_ids
        self.create(vals_list)
        to_unlink.unlink()

    @api.depends('state', 'child_ids.state', 'child_ids.model_id', 'child_ids.update_path',
                 'child_ids.update_m2m_operation', 'child_ids.resource_ref')
    def _compute_documents_remove_tag_ids(self):
        account_actions = self.filtered(lambda a: a.state == "documents_account_record_create")
        (self - account_actions).documents_remove_tag_ids = False
        for action in account_actions:
            tag_actions = action._document_get_tag_actions('remove')
            action.documents_remove_tag_ids = [a.resource_ref.id for a in tag_actions]

    def _inverse_documents_remove_tag_ids(self):
        vals_list = []
        to_unlink = self.env['ir.actions.server']
        for action in self:
            vals, unlink_ids = action._document_set_tag_actions('remove', action.documents_remove_tag_ids)
            vals_list += vals
            to_unlink |= unlink_ids
        self.create(vals_list)
        to_unlink.unlink()

    def _document_get_tag_actions(self, update_m2m_operation):
        self.ensure_one()
        return self.child_ids.filtered(lambda a:
            a.model_id.id == self.env['ir.model']._get_id('documents.document')
            and a.state == 'object_write'
            and a.update_path == 'tag_ids'
            and a.update_m2m_operation == update_m2m_operation
        )

    def _document_set_tag_actions(self, update_m2m_operation, tags):
        self.ensure_one()
        if self.state != "documents_account_record_create":
            return [], self.browse()

        actions = self._document_get_tag_actions(update_m2m_operation)
        existing_tags = actions.mapped('resource_ref')

        to_unlink = actions.filtered(lambda a: a.resource_ref not in tags)
        vals_list = [{
            'name': _('%(operation)s tag %(tag)s', operation=update_m2m_operation, tag=tag.name),
            'model_id': self.env['ir.model']._get_id('documents.document'),
            'state': 'object_write',
            'update_path': 'tag_ids',
            'update_m2m_operation': update_m2m_operation,
            'resource_ref': f'documents.tag,{tag.id}',
            'parent_id': self.id,
            'usage': 'ir_actions_server',
        } for tag in tags if tag not in existing_tags]
        return vals_list, to_unlink

    @api.constrains('model_id', 'state')
    def _check_document_account_check_model(self):
        document_model_id = self.env['ir.model']._get('documents.document')
        for action in self:
            if action.state == 'documents_account_record_create' and action.model_id != document_model_id:
                raise ValidationError(_('"New Journal Entry" can only be applied to Document.'))

    @api.constrains('parent_id', 'state', 'update_path')
    def _check_documents_account_record_create_child_ids(self):
        account_actions = self.filtered(lambda a: a.parent_id.state == 'documents_account_record_create')
        for action in account_actions:
            if action.update_path not in ('tag_ids', 'folder_id'):
                raise ValidationError(_('Only tag/folder updates are allowed as child actions.'))
            if action.parent_id.child_ids.mapped('update_path').count('folder_id') > 1:
                raise ValidationError(_('Only one folder move is allowed per action.'))

    @api.constrains('parent_id', 'state', 'resource_ref', 'update_path', 'update_m2m_operation')
    def _check_documents_tag_ids(self):
        account_actions = self.mapped("parent_id").filtered(
            lambda p: p.state == "documents_account_record_create")

        for action in account_actions:
            add_tags = set(action._document_get_tag_actions('add').mapped('resource_ref'))
            remove_tags = set(action._document_get_tag_actions('remove').mapped('resource_ref'))
            if conflicted_tags := add_tags & remove_tags:
                raise ValidationError(_(
                    'Cannot add and remove tags at the same time: %s',
                    ', '.join(tag.name for tag in conflicted_tags),
                ))

    @api.depends('model_id')
    def _compute_allowed_states(self):
        super()._compute_allowed_states()
        document_model_id = self.env['ir.model']._get('documents.document')
        for action in self:
            if action.model_id != document_model_id:
                action.allowed_states = [
                    state
                    for state in action.allowed_states
                    if state != 'documents_account_record_create']

    @api.depends('documents_account_create_model')
    def _compute_documents_account_journal_id(self):
        for action in self:
            if (action.documents_account_journal_id
                    and action.documents_account_journal_id not in action.documents_account_suitable_journal_ids):
                action.documents_account_journal_id = (
                    action.documents_account_suitable_journal_ids[0] if action.documents_account_suitable_journal_ids
                    else False)

    @api.depends('documents_account_create_model')
    @api.depends_context('company')
    def _compute_documents_account_suitable_journal_ids(self):
        company_journals = self.env['account.journal'].search(
            self.env['account.journal']._check_company_domain(self.env.company))
        if not company_journals:
            self.documents_account_suitable_journal_ids = False
            return
        bank_journals = company_journals.filtered(lambda journal: journal.type in ('bank', 'credit'))
        self.documents_account_suitable_journal_ids = False
        for action in self:
            if action.documents_account_move_type == 'statement':
                action.documents_account_suitable_journal_ids = bank_journals
            elif action.documents_account_move_type:
                action.documents_account_suitable_journal_ids = (
                        self.env['account.move']._get_suitable_journal_ids(action.documents_account_move_type))

    @api.depends('documents_account_create_model')
    def _compute_documents_account_move_type(self):
        self.documents_account_move_type = False
        for action in self:
            create_model = action.documents_account_create_model or ''
            if create_model.startswith(('account.move', 'account.bank.statement')):
                action.documents_account_move_type = create_model.split('.')[-1]

    def _generate_action_name(self):
        self.ensure_one()
        if self.state != 'documents_account_record_create':
            return super()._generate_action_name()
        options = dict(self._fields["documents_account_create_model"]._description_selection(self.env))
        translated_model_name = options.get(self.documents_account_create_model, "")
        if self.documents_account_journal_id:
            return _('%(model_name)s (%(journal_name)s)',
                     model_name=translated_model_name,
                     journal_name=self.documents_account_journal_id.name or '')
        return _('%(model_name)s', model_name=translated_model_name)

    def _name_depends(self):
        return super()._name_depends() + ["documents_account_create_model", "documents_account_journal_id.name"]

    def _run_action_documents_account_record_create_multi(self, eval_context=None):
        documents = eval_context.get('records') or eval_context.get('record')
        if not documents:
            return False

        journal_id = self.documents_account_journal_id or None
        if self.documents_account_create_model.startswith('account.move'):
            res = documents.account_create_account_move(self.documents_account_move_type, journal_id=journal_id)
        elif self.documents_account_create_model == 'account.bank.statement':
            res = documents.account_create_account_bank_statement(journal_id=journal_id)
        else:
            raise NotImplementedError

        return self._run_action_multi(eval_context=eval_context) or res
