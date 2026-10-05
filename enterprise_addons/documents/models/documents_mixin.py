# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import contextlib

from odoo import api, Command, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain


class DocumentsMixin(models.AbstractModel):
    """
    Inherit this mixin to automatically create a `documents.document` when
    an `ir.attachment` is linked to a record and add the default values when
    creating a document related to the model that inherits from this mixin.

    Override this mixin's methods to specify an owner, a folder, tags or
    access_rights for the document.

    Note: this mixin can be disabled with the context variable "no_document=True".
    """
    _name = 'documents.mixin'
    _description = "Documents creation mixin"
    # Field linking the record to its folder. When set, the folder is auto-linked to the record (res_model/res_id).
    _documents_record_folder_field_name = None

    document_count = fields.Integer(compute='_compute_document_count', string='Related Document Count')

    @api.model_create_multi
    def create(self, vals_list):
        # Automatically links folders to their related record, reset if shared
        records = super().create(vals_list)
        if self._documents_record_folder_field_name:
            records._documents_link_folders()
        return records

    def write(self, vals):
        # Overridden to synchronize folder linked records (update res_model/res_id on the folder).
        res = super().write(vals)
        if (field_name := self._documents_record_folder_field_name) and field_name in vals:
            self._documents_link_folders()
        return res

    def _documents_link_folders(self):
        field_name = self._documents_record_folder_field_name
        for record in self:
            folder_sudo = record.sudo()[field_name]
            if not folder_sudo:
                continue
            if folder_sudo.type != 'folder' or folder_sudo.shortcut_document_id:
                raise UserError(_(
                    '"%(document_name)s" cannot be linked to a record: only folders can.',
                    document_name=folder_sudo.display_name))
            if not folder_sudo.res_model:
                # "write" will raise an error if the folder is already assigned.
                folder_sudo.write({'res_model': record._name, 'res_id': record.id})
            elif (folder_sudo.res_model, folder_sudo.res_id) != (record._name, record.id):
                other_record = (
                    self.env[folder_sudo.res_model].browse(folder_sudo.res_id).exists()
                    if folder_sudo.res_model in self.env
                    else None
                )
                if other_record and other_record.has_access('read'):
                    raise UserError(_('This folder is already linked to %(other_record_name)s',
                                      other_record_name=other_record.display_name))
                raise UserError(_('This folder is already linked to another record.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_reset_linked_record(self):
        """Clear document record references (res_model, res_id) of deleted records."""
        # Skip documents linked to an attachment, as their res_model/res_id are derived from it
        # and their lifecycle is managed separately (moved to the Trash when the attachment is deleted).
        # The deleted records still reference their folder, the folder link check must be skipped.
        self.env['documents.document'].sudo().with_context(
            active_test=False, documents_skip_folder_link_check=True).search(
            [('res_model', '=', self._name), ('res_id', 'in', self.ids), ('attachment_id', '=', False)]).write({
            'res_model': False, 'res_id': False})

    def _compute_document_count(self):
        document_data = self.env['documents.document']._read_group(
            self._get_documents_domain(),
            groupby=['res_id'], aggregates=['__count'])
        mapped_data = dict(document_data)
        for record in self:
            record.document_count = mapped_data.get(record.id, 0)

    def _get_documents_domain(self):
        return Domain([('type', '!=', 'folder'), ('res_model', '=', self._name), ('res_id', 'in', self.ids)])

    def _get_document_vals(self, attachment):
        """
        Return values used to create a `documents.document`
        """
        self.ensure_one()
        document_vals = {}
        if self._check_create_documents():
            access_rights_vals = self._get_document_vals_access_rights()
            if set(access_rights_vals) - {'access_via_link', 'access_internal', 'is_access_via_link_hidden'}:
                raise ValueError("Invalid access right values")

            owner = self._get_document_owner()
            folder = self._get_document_folder()
            document_vals = {
                'attachment_id': attachment.id,
                'name': attachment.name or self.display_name,
                'folder_id': folder.id,
                'company_id': folder.company_id.id,
                'owner_id': owner.id if owner.active else False,
                'partner_id': self._get_document_partner().id,
                'tag_ids': [(6, 0, self._get_document_tags().ids)],
            } | access_rights_vals
        return document_vals

    def _get_document_vals_access_rights(self):
        """ Return access rights values to create a `documents.document`

        In the default implementation, we give the minimal permission and rely on the propagation of the folder
        permission but this method can be overridden to set more open rights.

        Authorized fields: access_via_link, access_internal, is_access_via_link_hidden.
        Note: access_ids are handled differently because when set, it prevents inheritance from the parent folder
        (see specific document override).
        """
        return {
            'access_via_link': 'none',
            'access_internal': 'none',
            'is_access_via_link_hidden': True,
        }

    def _get_document_owner(self):
        """ Return the owner value to create a `documents.document`

        In the default implementation, we return False as owner to avoid giving full access to a user and to rely
        instead on explicit access managed via `document.access` or via parent folder access inheritance but this
        method can be overridden to for example give the ownership to the current user.
        """
        return self.env['res.users']

    def _get_document_tags(self):
        return self.env['documents.tag']

    def _get_document_folder(self):
        return self.env['documents.document']

    def _get_document_partner(self):
        return self.env['res.partner']

    def _get_document_members(self):
        """ Add or remove members

        :returns: list of tuple (partner, (role, expiration_date)).
        :rtype: list
        """
        return []

    def _check_create_documents(self):
        return bool(self and self._get_document_folder())

    def _prepare_document_create_values_for_linked_records(
            self, res_model, vals_list, pre_vals_list):
        """ Set default value defined on the document mixin implementation of the related record if there are not
        explicitly set.

        :param str res_model: model referenced by the documents to consider
        :param list[dict] vals_list: list of values
        :param list[dict] pre_vals_list: list of values before _prepare_create_values (no permission inherited yet)

        Note:
        - This method doesn't override existing values (permission, owner, ...).
        - The related record res_model must inherit from DocumentsMixin
        """
        if self._name != res_model:
            raise ValueError(f'Invalid model {res_model} (expected {self._name})')

        related_record_by_id = self.env[res_model].browse([
            res_id for vals in vals_list if (res_id := vals.get('res_id'))]).grouped('id')
        for vals, pre_vals in zip(vals_list, pre_vals_list):
            if not vals.get('res_id') or vals.get('type') == 'folder':
                continue
            related_record = related_record_by_id.get(vals['res_id'])
            vals.update(
                {
                    'owner_id': pre_vals.get('owner_id', related_record._get_document_owner().id),
                    'partner_id': pre_vals.get('partner_id', related_record._get_document_partner().id),
                    'tag_ids': pre_vals.get('tag_ids', [(6, 0, related_record._get_document_tags().ids)]),
                } | {
                    key: value
                    for key, value in related_record._get_document_vals_access_rights().items()
                    if key not in pre_vals
                })
            if 'access_ids' in pre_vals:
                continue
            access_ids = vals.get('access_ids') or []
            access_per_partner = {access[2]['partner_id']: access for access in access_ids if access[2]}
            accesses_to_add = []
            for partner, mixin_access in related_record._get_document_members():
                if partner.id not in access_per_partner:
                    accesses_to_add.append((partner, mixin_access))
                    continue
                vals_access = access_per_partner[partner.id][2]
                if not vals_access.get('role'):
                    vals_access['role'], vals_access['expiration_date'] = mixin_access
            if accesses_to_add:
                access_ids.extend(
                    Command.create({
                        'partner_id': partner.id,
                        'role': role,
                        'expiration_date': expiration_date,
                    })
                    for partner, (role, expiration_date) in accesses_to_add
                )
            vals['access_ids'] = access_ids
        return vals_list

    def action_open_documents(self):
        self.ensure_one()
        linked_records_domain = self._get_documents_domain()
        folders = self.env['documents.document'].search(Domain('children_ids', 'any', linked_records_domain))
        default_folder = self.env['documents.document']
        with contextlib.suppress(AccessError):
            default_folder = self._get_document_folder()

        action = self.env['ir.actions.actions']._for_xml_id('documents.document_action_preference')
        domain = Domain('id', 'in', folders.ids) | linked_records_domain
        if default_folder and default_folder.user_permission != 'none':
            domain |= Domain('type', '=', 'folder') & Domain('id', 'child_of', default_folder.id)
        action['domain'] = domain
        action['context'] = {
            'default_res_id': self.id,
            'default_res_model': self._name,
            'documents_linked_records_domain': linked_records_domain,
            'searchpanel_default_user_folder_id': default_folder.id,
            'searchpanel_default_tag_ids': self._get_document_tags().ids,
        }
        return action
