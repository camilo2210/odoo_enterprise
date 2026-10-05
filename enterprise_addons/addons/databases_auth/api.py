import logging
from odoo.addons.databases.api import OdooDatabaseXmlrpcApi, OdooDatabaseApi


_logger = logging.getLogger(__name__)


def set_user_oauth_xmlrpc(self, db_user):
    _logger.info('Call xmlrpc set_user_oauth retrieving user_ids on %s, %s', self.host, db_user)
    user_ids = self.execute_kw('res.users', 'search', [('share', '=', False), ('login', '=', db_user.login)])
    if len(user_ids) > 1:
        # The only way to be in that position is having website installed and having done some shenanigans.
        # To mitigate that, we try harder to reduce the number of user.
        user_ids = self.execute_kw('res.users', 'search', [('share', '=', False), ('website_id', '=', False), ('login', '=', db_user.login)])
        user_ids = user_ids[:1]  # This shouldn't be necessary but we may never know 🤷‍♂️
    if not user_ids:
        _logger.info('Call xmlrpc set_user_oauth no user_ids found on %s for %s', self.host, db_user)
        return
    _logger.info('Call xmlrpc set_user_oauth on %s, %s, user_ids: %s', self.host, db_user, user_ids)
    return self.execute_kw('res.users', 'write', user_ids, {'oauth_uid': db_user.local_user_id.databases_sso_uid})


OdooDatabaseXmlrpcApi.set_user_oauth = set_user_oauth_xmlrpc


@OdooDatabaseApi.fallback_to_xmlrpc
def set_user_oauth(self, db_user):
    _logger.info('Call json2 set_user_oauth retrieving user_ids on %s, %s', self.host, db_user)
    user_ids = self.post_json2('res.users', 'search', domain=[('share', '=', False), ('login', '=', db_user.login)])
    if len(user_ids) > 1:
        # The only way to be in that position is having website installed and having done some shenanigans.
        # To mitigate that, we try harder to reduce the number of user.
        user_ids = self.post_json2('res.users', 'search', domain=[('share', '=', False), ('website_id', '=', False), ('login', '=', db_user.login)])
        user_ids = user_ids[:1]  # This shouldn't be necessary but we may never know 🤷‍♂️
    if not user_ids:
        _logger.info('Call json2 set_user_oauth no user_ids found on %s for %s', self.host, db_user)
        return
    _logger.info('Call json2 set_user_oauth on %s, %s, user_ids: %s', self.host, db_user, user_ids)
    return self.post_json2('res.users', 'write', ids=user_ids, vals={'oauth_uid': db_user.local_user_id.databases_sso_uid})


OdooDatabaseApi.set_user_oauth = set_user_oauth
