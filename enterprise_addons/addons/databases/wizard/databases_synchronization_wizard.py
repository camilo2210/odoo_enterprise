import logging
import re
from collections import defaultdict
from concurrent.futures import as_completed, ThreadPoolExecutor
from markupsafe import Markup
from socket import IPPROTO_TCP, gaierror, getaddrinfo
from urllib.parse import urlparse

from odoo import api, Command, fields, models
from odoo.fields import Domain
from odoo.addons.databases.models.project_project import get_database_api_keys

from ..api import ApiError, OdooComApi, OdooDatabaseApi, _humanize_version


_logger = logging.getLogger(__name__)


class DatabasesSynchronizationWizard(models.TransientModel):
    _name = 'databases.synchronization.wizard'
    _description = 'Database Synchronization Wizard'

    error_message = fields.Char(default='')
    summary_message = fields.Char(compute='_compute_summary_message')
    database_ids = fields.Many2many(
        comodel_name='project.project',
        domain=[('database_hosting', 'not in', (False, 'other'))],
    )
    created_database_ids = fields.Many2many(
        comodel_name='project.project',
        relation='databases_synchronization_wizard_created_databases_rel',
        domain=[('database_hosting', 'not in', (False, 'other'))],
    )
    property_definition = fields.Json()
    fetched_values = fields.Json()
    new_properties = fields.Json(string="New KPIs to add:")
    notify_user = fields.Boolean(default=False, required=True,
                                 help="Whether the user should be notified once the cron has finished synchronizing the databases")

    @api.depends('database_ids', 'created_database_ids')
    def _compute_summary_message(self):
        for record in self:
            record.summary_message = self.env._(
                "%(nb_new_dbs)s new databases, %(nb_updated_dbs)s updated.",
                nb_new_dbs=len(record.created_database_ids),
                nb_updated_dbs=len(record.database_ids)
            )

    def _open(self):
        # The wizard was used to select which property fields were to be added.
        # As they are now added inconditionally, is is bypassed and we just reload the client view.
        # We only show the error messages if any.
        # The wizard will be cleaned in saas~19.2, but we keep it in 19.0 and saas~19.1 to avoid changing the model in a stable version.
        action = {
            "type": "ir.actions.client",
            "tag": "soft_reload",
        }
        if self.error_message:
            action = {
                'type': 'ir.actions.act_window',
                'name': self.env._("Synchronization of %d databases", len(self.database_ids)),
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'views': [[False, 'form']],
            }
        return action

    def _can_update_from_odoo_com(self):
        ICP = self.env['ir.config_parameter'].sudo()
        apikey = ICP.get_str('databases.odoocom_apikey')
        return self.env.user.has_group('databases.group_databases_manager') and apikey

    def _do_update_from_odoocom(self):
        """
            - Get db info from odoo.com
            - Create missing dbs
            - Switch unconfigured on premise/paas to saas
            - Update saas dbs
            - Report configured on premise/paas dbs detected in saas as not updated
        """
        self.check_access("write")

        # Get db info from Odoo
        ICP = self.env['ir.config_parameter'].sudo()
        apihost = ICP.get_str('databases.odoocom_apihost') or 'https://www.odoo.com'
        apidb = ICP.get_str('databases.odoocom_apidb') or 'openerp'
        apikey = ICP.get_str('databases.odoocom_apikey')

        if not apikey:
            return

        odoocom_api = OdooComApi(apihost, apidb, apikey)
        try:
            databases = [db for db in odoocom_api.list_databases() if db['name'] != self.env.cr.dbname]
        except ApiError as e:
            self.error_message += self.env._(
                "Error while listing databases from %(dbname)s: %(message)s\n",
                dbname=apihost,
                message=e.args[0],
            )
            return

        # Create missing db
        Project = self.env['project.project']
        databases_by_url = {db['url']: db for db in databases}  # TODO: handle duplicate urls correctly
        existing_databases = Project.with_context(active_test=False).search([
            ('database_hosting', '!=', False),
            ('database_url', 'in', list(databases_by_url)),
        ])
        existing_urls = set(existing_databases.mapped('database_url'))
        template = Project._database_get_project_template()
        for db in databases:
            if db['url'] not in existing_urls:
                values = {
                    'name': db['name'],
                    'database_name': db['name'],
                    'database_hosting': 'saas',
                    'database_url': db['url'],
                    'database_api_login': db['login'],
                }
                if template:
                    self.created_database_ids |= template.action_create_from_template(values)
                else:
                    self.created_database_ids |= Project.create(values)

        # Update saas dbs
        saas_domain = [
            ('database_hosting', '=', 'saas'),
            ('database_url', 'in', list(databases_by_url)),
        ]
        # Switch unconfigured hosted db to saas
        hosting_should_be_saas = [
            ('database_hosting', 'in', ('paas', 'premise', 'other')),
            ('database_url', 'in', list(databases_by_url)),
            ('database_api_login', '=', False),
            ('database_api_key', '=', False),
        ]
        dbs_to_update = Project.with_context(active_test=False).search(Domain.OR([
            saas_domain,
            hosting_should_be_saas,
        ]))
        for db in dbs_to_update.try_lock_for_update():  # don't wait for db already updating
            db_info = databases_by_url[db.database_url]
            vals = {
                'database_hosting': 'saas',
                'database_name': db_info['name'],
                'database_api_login': db_info['login'],
            }
            if version := _humanize_version(db_info['version']):
                vals['database_version'] = version
            db.write(vals)

        self.database_ids |= self.created_database_ids

        saas_databases = existing_databases | self.created_database_ids | dbs_to_update
        if not saas_databases:
            return

        erroneous_dbs = []
        unreachable_tag_id = self.env.ref('databases.project_tag_db_unreachable').id
        odoocom_apikey = self.env['ir.config_parameter'].sudo().get_str('databases.odoocom_apikey', '')
        database_api_keys = get_database_api_keys(saas_databases, fallback=False)
        dbs_awaiting_api_key = saas_databases.filtered(lambda db: (
            db.active
            and not database_api_keys.get(db.id)
            # Avoid wasting 15s: unreachable dbs will most likely stay unreachable.
            # If it becomes reachable, we will try to create a key during the next update.
            and unreachable_tag_id not in db.tag_ids.ids
        ))
        for db in dbs_awaiting_api_key.try_lock_for_update():
            database_api_key = database_api_keys.get(db.id, odoocom_apikey)
            args = [db.database_url, db.database_name, db.database_api_login, database_api_key]
            if not all(args):
                continue
            db_api = OdooDatabaseApi(*args)
            key_name = ICP.get_str('databases.remote_api_key_description', f'Access for {self.env.company.name}')
            try:
                db.database_api_key = db_api.create_api_key(key_name, 'rpc')
            except ApiError:
                _logger.exception("Error while creating an API key on %r", db.database_name)
                erroneous_dbs.append(db.database_name)
        if erroneous_dbs:
            dbnames = ''.join(f'- {dbname}\n' for dbname in erroneous_dbs[:10])
            if len(erroneous_dbs) > 10:
                dbnames += self.env._('- … and %(nb_dbs)d more!\n', nb_dbs=len(erroneous_dbs) - 10)
            self.error_message += self.env._(
                "Error while creating an API key on %(nb_dbs)d databases:\n",
                nb_dbs=len(erroneous_dbs),
            ) + dbnames

    def _do_synchronize(self):
        self.check_access("write")

        if not self.database_ids:
            return self._open()

        immediate_sync_limit = self.env['ir.config_parameter'].sudo().get_int('databases.immediate_sync_limit', 300)

        dbs_to_process = self.database_ids[:immediate_sync_limit]
        dbs_to_postpone = self.database_ids[immediate_sync_limit:]

        # property.base.definition objects are readable only by role Settings
        database_kpi_base_definition_id = self.database_ids.sudo().database_kpi_base_definition_id
        database_kpi_base_definition_id.ensure_one()
        self.property_definition = database_kpi_base_definition_id.properties_definition

        unreachable_tag_id = self.env.ref('databases.project_tag_db_unreachable').id

        def _mark_db_unreachable(db, errors):
            db = db.sudo()
            db.write({'tag_ids': [Command.link(unreachable_tag_id)]})
            db.message_post(body=Markup('<br>').join(errors))

        database_api_keys = get_database_api_keys(dbs_to_process)
        db_by_url = {db.database_url: db for db in dbs_to_process}
        db_apis = []
        nb_failed_dbs = 0
        for db in dbs_to_process:
            database_api_key = database_api_keys.get(db.id, '')
            args = [db.database_url, db.database_name, db.database_api_login, database_api_key]
            if not all(args):
                nb_failed_dbs += 1
                _mark_db_unreachable(db, [self.env._(
                    "Error while connecting to %(url)s: We are missing the database name, the api login or the api key\n",
                    url=db.database_url,
                )])
                continue
            db_apis.append(OdooDatabaseApi(*args))

        # avoid flooding a server with tons of parallel requests in case several dbs are hosted on the same server.
        db_apis_per_ip, errors_by_url = _group_by_ips(db_apis, self.env._)
        nb_failed_dbs += len(errors_by_url)
        for db_url, errors in errors_by_url.items():
            _mark_db_unreachable(db_by_url[db_url], errors)

        with ThreadPoolExecutor(max_workers=8) as executor:
            db_apis_by_future = {executor.submit(_fetch_database_info, db_apis, self.env._): (db_apis, ip)
                                 for ip, db_apis in db_apis_per_ip.items()}
            for future in as_completed(db_apis_by_future):
                try:
                    results, errors_by_url = future.result()
                except Exception as e:  # noqa: BLE001
                    # Meaningful per-database errors are handled in `errors_by_url`.
                    # Any exception reaching here is unexpected/system-level,
                    # should not stop the synchronization and should be reported in the wizard.
                    db_apis, ip = db_apis_by_future[future]
                    host_names = ', '.join(db_api.host for db_api in db_apis)
                    _logger.warning('Error while fetching information from %s on %s: %s', host_names, ip, e)
                    self.error_message += self.env._("Error while fetching information from %(host_names)s on %(ip)s: %(message)s\n",
                                                     host_names=host_names, ip=ip, message=str(e))
                    continue

                for db_url, values in results.items():
                    db = db_by_url[db_url]
                    values.setdefault('tag_ids', []).append(Command.unlink(unreachable_tag_id))
                    kpi_summary = values.pop('kpi_summary', None)
                    if kpi_summary is not None:
                        self._write_kpis(db, kpi_summary)
                    users = values.pop('users', None)
                    if users is not None:
                        self._write_users(db, users)
                    db.sudo().write(values)  # databases_user should be able to synchronize, values keys are hardcoded

                nb_failed_dbs += len(errors_by_url)
                for db_url, errors in errors_by_url.items():
                    _mark_db_unreachable(db_by_url[db_url], errors)

        self.action_add_metrics_to_dashboard()
        self.write({'new_properties': {}})

        if nb_failed_dbs > 0:
            self.error_message += self.env._("%(nb_failed_dbs)s databases could not be synchronized.\n",
                                             nb_failed_dbs=nb_failed_dbs)

        if dbs_to_postpone:
            dbs_to_postpone.sudo().database_last_synchro = False
            self.notify_user = True
            self.env.ref('databases.ir_cron_synchronize_databases')._trigger()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': self.env._("Synchronization of %d databases", len(self.database_ids)),
                    'message': self.env._("Database synchronization is running in the background. "
                                          "You will be notified upon completion."),
                    'type': 'info',
                    'sticky': False,
                    'next': self._open(),
                },
            }
        return self._open()

    def _write_users(self, db, users):
        # sudo in this method are there to allow databases_user to synchronize
        users = {u['login']: u for u in users}
        existing_users = db.database_user_ids
        common_users = existing_users.filtered(lambda u: u.login in users)
        missing_logins = set(users) - set(existing_users.mapped('login'))
        users_to_delete = existing_users - common_users

        users_to_delete.sudo().unlink()
        existing_users.sudo().create([
            {
                'project_id': db.id,
                'login': user['login'],
                'name': user['name'],
                'latest_authentication': user['login_date']
            }
            for user in users.values() if user['login'] in missing_logins
        ])
        for user in common_users:
            user_data = users[user.login]
            user.sudo().write({
                'name': user_data['name'],
                'latest_authentication': user_data['login_date'],
            })

    def _write_kpis(self, db, kpi_summary):
        property_definition = {x['name']: x for x in self.property_definition or []}
        kpi_properties = {}
        for kpi in kpi_summary:
            if kpi['id'] == 'documents.inbox':
                if db.database_fetch_documents:
                    db.sudo().database_nb_documents = kpi['value']  # databases_user should be able to synchronize, values keys are hardcoded
                continue

            if kpi['id'].startswith('account_move_type.') and not db.database_fetch_draft_entries:
                continue

            if kpi['id'].startswith('account_return.') and not db.database_fetch_tax_returns:
                continue

            # property names must match odoo.orm.utils.regex_alphanumeric
            kpi_id = re.sub(r'[^a-z0-9]', '_', kpi['id'].lower())
            if kpi_id not in property_definition:
                property_definition[kpi_id] = {
                    'name': kpi_id,
                    'string': kpi['name'],
                }
                if kpi['type'] == 'integer':
                    property_definition[kpi_id].update({
                        'type': 'integer',
                        'default': 0,
                    })
                elif kpi['type'] == 'kyc_status':
                    property_definition[kpi_id].update({
                        'type': 'selection',
                        'default': False,
                        'selection': [
                            ['not_done', '🔴'],
                            ['incomplete', '🟡'],
                            ['done', '🟢'],
                        ],
                    })
                elif kpi['type'] == 'return_status':
                    property_definition[kpi_id].update({
                        'type': 'selection',
                        'default': False,
                        'selection': [
                            ['late', '🔴'],
                            ['longterm', '⚪'],
                            ['to_do', '🟡'],
                            ['to_submit', '🟢⚪'],
                            ['done', '🟢'],
                        ],
                    })

            kpi_properties[kpi_id] = kpi['value']

        # property.base.definition objects are readable only by role Settings
        database_kpi_base_definition_id = self.database_ids.sudo().database_kpi_base_definition_id
        database_kpi_base_definition_id.ensure_one()
        previous_kpi_ids = {x['name'] for x in database_kpi_base_definition_id.properties_definition}
        self.write({
            'new_properties': {kpi_id: {'label': kpi['string'], 'checked': True}
                               for kpi_id, kpi in property_definition.items() if kpi_id not in previous_kpi_ids},
            'property_definition': list(property_definition.values()),
        })

        self.fetched_values = {
            **(self.fetched_values or {}),
            db.id: kpi_properties,
        }

    def action_add_metrics_to_dashboard(self):
        if not self.database_ids:
            return

        # property.base.definition objects are readable only by role Settings
        database_kpi_base_definition_id = self.database_ids.sudo().database_kpi_base_definition_id
        database_kpi_base_definition_id.ensure_one()
        existing_keys = {x['name'] for x in database_kpi_base_definition_id.properties_definition}
        properties_definition = [x for x in self.property_definition or []
                                 if x['name'] in existing_keys or self.new_properties[x['name']]['checked']]

        # sort the properties definition on the prefix of the name first, then on the string
        prefix_order = ('account_journal_type', 'account_move_type', 'account_return')
        properties_definition = sorted(properties_definition, key=lambda x: (
            # index of the first matching prefix, defaulting to the end
            next((i for i, prefix in enumerate(prefix_order) if x['name'].startswith(prefix)), len(prefix_order)),
            # then the displayed name
            x['string'],
        ))

        database_kpi_base_definition_id.write({
            'properties_definition': properties_definition,
        })

        for db in self.database_ids:
            fetched_values = (self.fetched_values or {}).get(str(db.id))  # JSON keys are strings
            db.sudo().write({'database_kpi_properties': fetched_values})

        action = {
            "type": "ir.actions.client",
            "tag": "soft_reload",
        }
        return action


def _group_by_ips(db_apis, translate):
    groups = defaultdict(list)
    errors_by_url = defaultdict(list)
    for db_api in db_apis:
        hostname = urlparse(db_api.host).hostname
        try:
            addrinfo = getaddrinfo(hostname, None, proto=IPPROTO_TCP)
        except gaierror as e:
            errors_by_url[db_api.host].append(translate("Error while resolving %(url)s: %(exception)s\n", url=db_api.host, exception=str(e)))
            continue
        if not addrinfo:
            errors_by_url[db_api.host].append(translate("Error while resolving %(url)s: found no IP\n", url=db_api.host))
            continue

        _family, _type, _proto, _canonname, (ip, _port, *_) = sorted(addrinfo)[0]  # sort IPv4 before IPv6
        groups[ip].append(db_api)
    return groups, errors_by_url


def _fetch_database_info(db_apis, translate):
    results = {}
    errors_by_url = defaultdict(list)
    for db_api in db_apis:
        results[db_api.host] = {
            'database_last_synchro': fields.Datetime.now(),
            'database_nb_synchro_errors': 0,
        }
        if version := OdooDatabaseApi.fetch_version(db_api.host):
            results[db_api.host]['database_version'] = version

        try:
            results[db_api.host]['users'] = db_api.list_internal_users()
        except ApiError as e:
            errors_by_url[db_api.host].append(translate(
                "Error while getting users from %(dbname)s: %(message)s\n",
                dbname=db_api.database,
                message=e.args[0],
            ))

        try:
            results[db_api.host]['kpi_summary'] = db_api.get_kpi_summary()
        except ApiError as e:
            errors_by_url[db_api.host].append(translate(
                "Error while getting KPIs from %(dbname)s: %(message)s\n",
                dbname=db_api.database,
                message=e.args[0],
            ))

    return results, errors_by_url
