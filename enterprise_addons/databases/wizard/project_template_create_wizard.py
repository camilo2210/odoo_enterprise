from odoo import api, fields, models
from odoo.tools import SQL
from odoo.tools.sql import column_exists, create_column


def get_wizard_api_keys(wizards):
    """Retrieve the api keys to use for those records."""
    if not wizards.ids:
        return {}

    env = wizards.env
    wizard_api_keys = dict(env.execute_query(SQL(
        """
        SELECT id, database_api_key
        FROM project_template_create_wizard
        WHERE id in %s AND COALESCE(database_api_key, '') != ''
        """,
        tuple(wizards.ids),
    )))
    return wizard_api_keys


class ProjectTemplateCreateWizard(models.TransientModel):
    _inherit = 'project.template.create.wizard'

    database_hosting = fields.Selection(
        selection=[
            ('saas', 'Odoo Online'),
            ('paas', 'Odoo.sh'),
            ('premise', 'On Premise'),
            ('other', 'Outside of Odoo'),
        ],
        string='Hosting',
    )
    database_name = fields.Char(string="Database Name")
    database_url = fields.Char(string="Database URL")
    database_api_login = fields.Char(string="Database API Login")
    database_api_key = fields.Char(
        string="Database API Key",
        compute='_compute_database_api_key',
        inverse='_inverse_database_api_key',
        store=False,  # prevent the ORM from querying the field itself
    )
    database_fetch_documents = fields.Boolean("Fetch Documents", default=True)
    database_fetch_draft_entries = fields.Boolean("Fetch Draft Journal Entries", default=True)
    database_fetch_tax_returns = fields.Boolean("Fetch Tax Returns", default=True)

    def init(self):
        # The field is a compute that shouldn't be discoverable by the orm itself
        # Therefore we need to create the column manually
        if not column_exists(self.env.cr, 'project_template_create_wizard', 'database_api_key'):
            create_column(self.env.cr, 'project_template_create_wizard', 'database_api_key', 'varchar')
        return super().init()

    def _compute_database_api_key(self):
        wizard_ids_with_keys = get_wizard_api_keys(self).keys()
        wizard_with_keys = self.filtered(lambda wizard: wizard.id in wizard_ids_with_keys)
        # prefill some *** to not confuse users.
        wizard_with_keys.database_api_key = '****************************************'
        (self - wizard_with_keys).database_api_key = ''

    def _inverse_database_api_key(self):
        wizard_to_key = tuple(
            (wizard.id, wizard.database_api_key or '')  # allow the user to clear the key
            for wizard in self
            # prevent user to mess with their key by removing a few stars from the field by mistake
            if '******' not in (wizard.database_api_key or '')
        )
        if not wizard_to_key:
            return
        self.env.cr.execute(
            SQL(
                """
                UPDATE project_template_create_wizard
                SET database_api_key = db.database_api_key
                FROM (VALUES %s) AS db(id, database_api_key)
                WHERE project_template_create_wizard.id = db.id
                """,
                SQL(",").join(wizard_to_key)
            )
        )
        self.invalidate_recordset(['database_api_key'])

    def _get_template_whitelist_fields(self):
        whitelist = super()._get_template_whitelist_fields()
        if self.env.context.get('databases_template'):
            whitelist.extend([
                'database_hosting',
                'database_name',
                'database_url',
                'database_api_login',
                'database_api_key',
                'database_fetch_documents',
                'database_fetch_draft_entries',
                'database_fetch_tax_returns',
            ])
        return whitelist

    def _create_project_from_template(self):
        project_id = super()._create_project_from_template()
        if 'database_api_key' in self._get_template_whitelist_fields():
            wizard_api_key = get_wizard_api_keys(self).get(self.id, '')
            project_id.database_api_key = wizard_api_key
        return project_id

    @api.model
    def action_open_template_view(self):
        action = super().action_open_template_view()

        if self.env.context.get('databases_template'):
            view = self.env.ref('databases.project_project_view_form_simplified_template', raise_if_not_found=False)
            if view:
                action['views'] = [(view.id, 'form')]

        return action
