from odoo.tests import tagged, TransactionCase
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestOauthClient(TransactionCase):

    def test_client_id_is_immutable(self):
        client = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': "https://client.example.com/callback",
        })

        with self.assertRaises(UserError):
            client.client_id = 'new client id'

    def test_localhost_redirect_uri_is_stored_as_an_ip(self):
        client = self.env['oauth.client'].create({
            'client_name': 'Test Client',
            'redirect_uris': "http://localhost:8080/cb\nhttps://client.example.com/callback",
        })
        self.assertEqual(
            client.redirect_uris.splitlines(),
            ["http://127.0.0.1:8080/cb", "https://client.example.com/callback"],
        )

        client.redirect_uris = "http://LocalHost/cb"
        self.assertEqual(client.redirect_uris, "http://127.0.0.1/cb")
