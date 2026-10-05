from . import models
from . import controllers
from . import wizard
from odoo.tools import SQL


def _documents_account_post_init(env):
    env['account.journal'].search(
        [('id', 'not in', env['documents.account.folder.setting']._search([]).select(SQL("journal_id")))]
    )._documents_configure_sync()
