import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _set_oauth_to_remote_db(self, users):
        # sudo to allow user to setup its own oauth if he already has a user in the remote db
        self.env['databases.manage_users.wizard'].sudo().create({
            'mode': 'invite',
            'database_ids': self.ids,
            'user_ids': users.ids,
        })._set_oauth_to_remote_dbs()

    def action_database_connect(self):
        self.ensure_one()
        if (
            self.database_hosting == 'saas'
            and self.env['ir.config_parameter'].sudo().get_bool('databases.saas_single_sign_on', False)
        ):
            if not self.env.user.databases_sso_uid:
                # Smooth path setting the databases_sso_uid locally if none is there and to the remote db automatically
                # and then connecting the user to the db directly
                return self.env.user._get_action_retrieve_oauth(self.id)
            self._set_oauth_to_remote_db(self.env.user)  # we don't know if the oauth is set or not

        return super().action_database_connect()
