from collections import defaultdict

from odoo import api, fields, models
from odoo.tools import frozendict


class DocumentsAccessTracking(models.Model):
    _name = 'documents.access.tracking'
    _description = 'Document Access Tracking'
    _log_access = False

    changes = fields.Json(string='Changes need to be tracked', required=True)
    documents = fields.Json(string='Impacted Document Ids', required=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)

    @api.model
    def _create_access_tracking(self, changes_by_document_dict):
        documents_by_changes = defaultdict(list)
        for document_id, changes in changes_by_document_dict.items():
            documents_by_changes[frozendict(changes)].append(document_id)

        batch_size = self.env['ir.config_parameter'].sudo().get_int('documents.tracking_batch_size') or 500
        for changes, documents in documents_by_changes.items():
            self.sudo().create([
                {
                    'changes': dict(changes),
                    'documents': documents[offset: offset + batch_size],
                    'user_id': self.env.user.id,
                } for offset in range(0, len(documents), batch_size)
            ])

        self.env.ref('documents.ir_cron_documents_access_tracking')._trigger()

    @api.model
    def _cron_generate_tracking(self):
        tracking_id = self.search([], limit=1)
        if not tracking_id:
            self.env['ir.cron']._commit_progress(remaining=0)
            return

        tracking_id._create_message_track()
        tracking_id.unlink()
        self.env['ir.cron']._commit_progress(processed=len(tracking_id), remaining=self.search_count([]))

    def _create_message_track(self):
        self.ensure_one()
        document_ids = self.env['documents.document'].browse(self.documents)
        if initial_values := self._get_initial_values():
            if 'members' in self.changes or 'groups' in self.changes:
                track_body = self._get_members_change_template_body()
                document_ids._track_set_log_message(track_body)
            documents_as_user = document_ids.with_user(self.user_id)
            documents_as_user._track_add(initial_values)
            # fire now finalize to move sequentially in posting messages
            documents_as_user._track_finalize()
        else:
            track_body = self._get_members_change_template_body()
            document_ids.with_user(self.user_id)._message_log_batch(
                bodies={doc_id: track_body for doc_id in document_ids.ids}
            )

    def _get_initial_values(self):
        self.ensure_one()
        fields_list = ['access_internal', 'access_via_link', 'is_access_via_link_hidden']
        common_values = {
            field: self.changes[field] for field in fields_list if field in self.changes
        }
        return {doc_id: common_values for doc_id in self.documents if common_values}

    def _get_members_change_template_body(self):
        self.ensure_one()
        # TDE note: use with_source
        return self.env['ir.qweb']._render('documents.tracking_access_members_change', {
            **{
                access_type: {
                    **({'members': self.changes['members'][action]} if self.changes.get('members') else {}),
                    **({'groups': self.changes['groups'][action]} if self.changes.get('groups') else {}),
                } for access_type, action in [
                    ('created_access', 'added'),
                    ('updated_access', 'updated'),
                    ('removed_access', 'removed')]
                if self.changes.get('members', {}).get(action) or self.changes.get('groups', {}).get(action)
            },
            'partner_map': self.changes.get('members') and self._get_partners_or_groups_mapping('members'),
            'group_map': self.changes.get('groups') and self._get_partners_or_groups_mapping('groups'),
        }, lang=self.user_id.lang, minimal_qcontext=True)

    def _get_partners_or_groups_mapping(self, type):
        self.ensure_one()
        type_model = 'res.partner' if type == 'members' else 'res.group.functional'
        type_map = {}
        type_dict = self.changes[type]
        for operation in ['added', 'updated']:
            # must cast into int because fields.Json set all keys in string
            record_ids = self.env[type_model].browse([int(id) for id in type_dict[operation]])
            type_map.update(dict(zip(type_dict[operation].keys(), record_ids)))

        record_ids = self.env[type_model].browse(type_dict['removed'])
        type_map.update(dict(zip(type_dict['removed'], record_ids)))

        return type_map
