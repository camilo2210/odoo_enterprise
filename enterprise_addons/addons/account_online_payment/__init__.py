import logging
from odoo.exceptions import UserError

from . import controllers
from . import models
from . import wizard

_logger = logging.getLogger(__name__)


def _post_init_hook(env):
    links = env['account.online.link'].search([])
    for link in links:
        try:
            link._update_connection_status()
        except UserError as e:
            _logger.warning("Failed to update connection status for account online link %s: %s", link.client_id, e)
