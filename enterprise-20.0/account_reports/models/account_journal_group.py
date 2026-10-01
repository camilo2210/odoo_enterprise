from collections.abc import Collection

from odoo import api, models


class AccountJournalGroup(models.Model):
    _inherit = "account.journal.group"

    def _cache_local_gaap(self):
        local_gaap = self.browse(['local_gaap'])
        self._fields['name']._update_cache(local_gaap, self.env._("Local Gaap"))
        self._fields['sequence']._update_cache(local_gaap, 0)
        self._fields['included_journal_ids']._update_cache(local_gaap, tuple(self.env['account.journal'].with_context(active_test=False).search([('journal_group_id', '=', False)]).ids))

    @api.private
    def fetch(self, field_names: Collection[str] | None = None) -> None:
        real_ids = self._ids
        if 'local_gaap' in self._ids:
            real_ids = [id_ for id_ in self._ids if id_ != 'local_gaap']
            self._cache_local_gaap()
        super(AccountJournalGroup, self.browse(real_ids)).fetch(field_names)
