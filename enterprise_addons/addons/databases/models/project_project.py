import logging

from odoo import api, Command, fields, models, modules
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL
from odoo.tools.parse_version import parse_version
from odoo.tools.sql import column_exists, create_column

from ..api import ApiError, OdooDatabaseApi

_logger = logging.getLogger(__name__)


def get_database_api_keys(databases, fallback=True):
    """Retrieve the api keys to use for those records. Saas database without key will be provided the odoocom apikey"""
    if not databases.ids:
        return {}

    env = databases.env
    database_api_keys = dict(env.execute_query(SQL(
        """
        SELECT id, database_api_key
        FROM project_project
        WHERE id in %s AND COALESCE(database_api_key, '') != ''
        """,
        tuple(databases.ids),
    )))
    if not fallback:
        return database_api_keys

    odoocom_apikey = env['ir.config_parameter'].sudo().get_str('databases.odoocom_apikey', '')
    for db in databases:
        if not database_api_keys.get(db.id):
            database_api_keys[db.id] = odoocom_apikey

    return database_api_keys


class ProjectProject(models.Model):
    _inherit = 'project.project'

    database_hosting = fields.Selection(
        selection=[
            ('saas', 'Odoo Online'),
            ('paas', 'Odoo.sh'),
            ('premise', 'On Premise'),
            ('other', 'Outside of Odoo'),
        ],
        string='Hosting',
        copy=False,
    )
    database_name = fields.Char(string="Database Name", copy=False)
    database_url = fields.Char(string="Database URL", copy=False)
    database_version = fields.Char(string="Database Version", copy=False)
    database_api_login = fields.Char(string="Database API Login", groups="databases.group_databases_user", copy=False)
    database_api_key = fields.Char(
        string="Database API Key",
        groups="databases.group_databases_manager",
        copy=False,
        compute='_compute_database_api_key',
        inverse='_inverse_database_api_key',
        search='_search_database_api_key',
        store=False,  # prevent the ORM from querying the field itself
    )
    database_api_key_to_use = fields.Char(groups="databases.group_databases_manager", compute='_compute_database_api_key_to_use')  # unused: TODO: to remove in master
    database_fetch_documents = fields.Boolean("Fetch Documents", default=True)
    database_fetch_draft_entries = fields.Boolean("Fetch Draft Journal Entries", default=True)
    database_fetch_tax_returns = fields.Boolean("Fetch Tax Returns", default=True)
    database_kpi_properties = fields.Properties("Metrics", definition='database_kpi_base_definition_id.properties_definition', copy=False)
    database_kpi_base_definition_id = fields.Many2one(
        'properties.base.definition',
        compute='_compute_database_kpi_base_definition_id',
        compute_sql='_compute_sql_database_kpi_base_definition_id',
        compute_sudo=True,
    )
    database_user_ids = fields.One2many('databases.user', 'project_id', string='Database Users', copy=False)
    database_last_synchro = fields.Datetime("Last Synchronization", readonly=True, copy=False)
    database_nb_synchro_errors = fields.Integer("Synchronization Errors Count", readonly=True, copy=False)
    database_nb_documents = fields.Integer('Amount of documents in Inbox', copy=False)
    database_nb_users = fields.Integer('Amount of Users', compute='_compute_database_nb_users', store=True)
    database_can_access = fields.Boolean(compute='_compute_database_can_access')

    user_is_database_user = fields.Boolean(compute='_compute_user_is_database_user', search='_search_user_is_database_user')

    _database_url_unique = models.UniqueIndex('(database_url)', "Hey, this URL is already hooked up to a database!")
    _database_url_required = models.Constraint(
        "CHECK(database_hosting IS NULL OR database_url IS NOT NULL)",
        "Uh-oh! It seems we are missing a url for a database!",
    )

    def init(self):
        # The field is a compute that shouldn't be discoverable by the orm itself
        # Therefore we need to create the column manually
        if not column_exists(self.env.cr, 'project_project', 'database_api_key'):
            create_column(self.env.cr, 'project_project', 'database_api_key', 'varchar')
        return super().init()

    def _compute_database_api_key(self):
        db_ids_with_keys = get_database_api_keys(self, fallback=False).keys()
        db_with_keys = self.filtered(lambda db: db.id in db_ids_with_keys)
        # prefill the value for the form view.
        # Add some *** to not confuse users.
        db_with_keys.database_api_key = '****************************************'
        (self - db_with_keys).database_api_key = ''

    def _inverse_database_api_key(self):
        db_to_key = tuple(
            (database.id, database.database_api_key or '')  # allow the user to clean the key to leverage odoocom key
            for database in self
            # prevent user to mess with their key by removing a few stars from the field by mistake
            if '******' not in (database.database_api_key or '')
        )
        if not db_to_key:
            return
        self.env.cr.execute(
            SQL(
                """
                UPDATE project_project
                SET database_api_key = db.database_api_key
                FROM (VALUES %s) AS db(id, database_api_key)
                WHERE project_project.id = db.id
                """,
                SQL(",").join(db_to_key)
            )
        )
        self.invalidate_recordset(['database_api_key'])

    def _search_database_api_key(self, operator, value):
        # To prevent any attempt to discover the key value, only looking against falsy value is supported
        if value or operator not in ('=', '!='):
            return NotImplemented
        query = SQL("SELECT id FROM project_project WHERE COALESCE(database_api_key, '') = ''")
        return fields.Domain('id', 'in' if operator == '=' else 'not in', query)

    def _compute_database_api_key_to_use(self):
        self.database_api_key_to_use = ''

    def _compute_database_kpi_base_definition_id(self):
        self.database_kpi_base_definition_id = self.env['properties.base.definition'] \
            ._get_definition_for_property_field(self._name, 'database_kpi_properties')

    def _compute_sql_database_kpi_base_definition_id(self, table):
        parent = self.env['properties.base.definition'] \
            ._get_definition_id_for_property_field(self._name, 'database_kpi_properties')
        return SQL("%s", parent)

    @api.depends('database_user_ids')
    def _compute_database_nb_users(self):
        users_count_per_database = dict(
            self.env['databases.user']._read_group(
                [('project_id', 'in', self.ids)],
                ['project_id'],
                ['__count'],
            )
        )
        for db in self:
            db.database_nb_users = users_count_per_database.get(db, 0)

    @api.depends('database_user_ids.local_user_id')
    @api.depends_context('user')
    def _compute_database_can_access(self):
        databases_with_current_user = self.env['databases.user']._read_group(
            [('login', '=', self.env.user.login)],
            aggregates=['project_id:recordset'],
        )[0][0]
        for db in self:
            db.database_can_access = db in databases_with_current_user

    @api.depends_context('uid')
    def _compute_user_is_database_user(self):
        self.user_is_database_user = self.env.user.has_group('databases.group_databases_user')

    def _search_user_is_database_user(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return Domain(self.env.user.has_group('databases.group_databases_user'))

    @api.onchange('database_url')
    def _onchange_database_url(self):
        self.database_url = self._normalize_user_url(self.database_url)

    def _normalize_user_url(self, url):
        if not url:
            return False

        url = url.strip()
        if not url or url.startswith(('http://', 'https://')):
            return url

        if url.startswith('//'):
            return 'https:' + url

        return 'https://' + url

    @api.model_create_multi
    def create(self, vals_list):
        parent = self.env['properties.base.definition'] \
            ._get_definition_id_for_property_field(self._name, 'database_kpi_properties')

        for vals in vals_list:
            # set the properties definition foreign key
            vals['database_kpi_base_definition_id'] = parent

            if not vals.get('database_hosting'):
                # this isn't a database
                continue

            if not vals.get('privacy_visibility'):
                # Avoid random user to be able to access the database info and kpis
                vals['privacy_visibility'] = 'followers'

        return super().create(vals_list)

    def action_open_self(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_id': self.id,
            'res_model': self._name,
        }

    @api.model
    def _cron_synchronize_all_databases_with_odoocom(self):
        """ Fetch the list from the Odoo.com SaaS if configured so, and trigger a synchronization of all the databases """
        wizard = self.env['databases.synchronization.wizard'].create({})
        wizard._do_update_from_odoocom()

        self.env.ref('databases.ir_cron_synchronize_databases')._trigger()

        if not modules.module.current_test:
            self.env['ir.cron']._commit_progress(remaining=0)

    @api.model
    def _cron_synchronize_all_databases(self):
        database_to_synchronize = self.env['project.project'].search([
            ('database_hosting', 'not in', (False, 'other')),
            ('database_nb_synchro_errors', '<', 5),
            '|',
                ('database_last_synchro', '=', False),
                ('database_last_synchro', '<=', 'now -1d'),
        ], order='database_last_synchro NULLS FIRST')
        if not modules.module.current_test:
            self.env['ir.cron']._commit_progress(remaining=len(database_to_synchronize))

        notifiable_wizards = self.env['databases.synchronization.wizard'].search([
            ('notify_user', '=', True),
        ])

        for database in database_to_synchronize:
            db_wizard = self.env['databases.synchronization.wizard'].create({
                'database_ids': [Command.link(database.id)],
            })
            try:
                db_wizard._do_synchronize()
            except Exception:
                _logger.exception('Error during synchronization of database %r', database.database_url)
                if not modules.module.current_test:
                    self.env['ir.cron']._rollback_progress()
                database.database_nb_synchro_errors += 1
            else:
                if db_wizard.error_message:
                    database.database_nb_synchro_errors += 1

            for wizard in notifiable_wizards.filtered('notify_user'):
                if all(wizard.database_ids.mapped('database_last_synchro')):
                    wizard.notify_user = False
                    wizard.create_uid._bus_send('simple_notification', {
                        'title': self.env._("Synchronization of %d databases", len(wizard.database_ids)),
                        'message': wizard.summary_message,
                        'type': 'success',
                        'sticky': True,
                    })
            if not modules.module.current_test:
                self.env['ir.cron']._commit_progress(processed=1)

    @api.model
    def _get_databases_to_sync(self, dbs=None):
        # We first synchronize the databases the current user can log into, since these are the ones
        # they are most likely to use right away and some synchronizations may end up queued.
        common_domain = [('database_hosting', 'in', ('saas', 'paas', 'premise'))]
        if dbs is not None:
            common_domain += [('id', 'in', dbs.ids)]
        # We do 2 searchs to avoid the hasle of a SQL query with a weird order clause that would requires a left join
        user_dbs = self.env['project.project'].search(
            fields.Domain.AND([common_domain, [('database_user_ids.login', '=', self.env.user.login)]]),
            order='database_last_synchro NULLS FIRST, id',
        )
        other_dbs = self.env['project.project'].search(
            fields.Domain.AND([common_domain, [('id', 'not in', user_dbs.ids)]]),
            order='database_last_synchro NULLS FIRST, id',
        )
        return user_dbs + other_dbs

    @api.model
    def action_synchronize_all_databases(self):
        """
        Synchronize all the databases, and fetch the list from the Odoo.com SaaS if configured so.
        If active_ids is not empty, consider that the user only wants to synchronize these specific databases,
        and fallback to action_database_synchronize.
        """
        if active_ids := self.env.context.get('active_ids'):
            return self.env['project.project'].browse(active_ids).action_database_synchronize()

        all_databases = self.env['project.project']._get_databases_to_sync()
        wizard = self.env['databases.synchronization.wizard'].create({'database_ids': all_databases.ids})
        if wizard._can_update_from_odoo_com():
            wizard._do_update_from_odoocom()
        return wizard._do_synchronize()

    def action_database_synchronize(self):
        """ Synchronize the kpis from the selected databases """
        dbs = self.env['project.project']._get_databases_to_sync(self)
        wizard = self.env['databases.synchronization.wizard'].create({'database_ids': dbs.ids})
        wizard_action = wizard._do_synchronize()
        if len(self) == 1 and wizard.error_message:
            raise UserError(wizard.error_message.strip())
        return wizard_action

    def _get_connect_url(self):
        self.ensure_one()
        url = None
        if self.database_hosting == 'other':
            # Stored outside of Odoo, just redirect to the url
            url = self.database_url

        if not url and self.database_hosting == 'saas':
            odoocom_url = self.env['ir.config_parameter'].sudo().get_str('databases.odoocom_apihost', 'https://www.odoo.com')
            database_api_key = get_database_api_keys(self).get(self.id, '')
            db_api = OdooDatabaseApi(self.database_url, self.database_name, self.database_api_login, database_api_key)
            try:
                db_uuid = db_api.get_database_uuid()
            except ApiError:
                # Either server unreachable or most probably no permissions to read ir.config_parameter
                pass
            else:
                url = f'{odoocom_url}/my/databases/connect/{db_uuid}'

        if not url and self._database_version_gte('saas~17.2'):
            # Supported since odoo/odoo@c63d14a0485a553b74a8457aee158384e9ae6d3f
            url = f'{self.database_url}/odoo'

        if not url:
            url = f'{self.database_url}/web'

        return url

    def action_database_connect(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self._get_connect_url(),
            'target': 'new',
        }

    def action_database_invite_users(self):
        return {
            'name': 'Invite Users',
            'type': 'ir.actions.act_window',
            'res_model': 'databases.manage_users.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mode': 'invite',
                'default_database_ids': self.ids,
            },
        }

    def action_database_remove_users(self, default_user_ids=None):
        return {
            'name': 'Remove Users',
            'type': 'ir.actions.act_window',
            'res_model': 'databases.manage_users.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mode': 'remove',
                'default_database_ids': self.ids,
                'default_user_ids': default_user_ids if default_user_ids else [],
            },
        }

    def _database_version_gte(self, version):
        return parse_version(self.database_version) >= parse_version(version)

    def _database_get_project_template(self):
        template_id = self.env['ir.config_parameter'].sudo().get_int('databases.odoocom_project_template')
        return self.browse(template_id).exists()
