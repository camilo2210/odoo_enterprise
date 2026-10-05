# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import HttpCase, JsonRpcException
from odoo.tools import mute_logger

from .common import SpreadsheetTestCommon


class TestSpreadsheetPublicSharing(SpreadsheetTestCommon, HttpCase):

    def test_get_data_public_user_with_view_token(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'view'})
        response = self.url_open(
            f'/spreadsheet/data/documents.document/{spreadsheet.id}/{spreadsheet.access_token}'
        )
        self.assertTrue(response.ok)
        self.assertFalse(response.json()['has_write_access'])

    def test_get_data_public_user_with_edit_token(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        response = self.url_open(
            f'/spreadsheet/data/documents.document/{spreadsheet.id}/{spreadsheet.access_token}'
        )
        self.assertTrue(response.ok)
        self.assertTrue(response.json()['has_write_access'])

    def test_dispatch_public_user_with_edit_token(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        revision = self.new_revision_data(spreadsheet)
        result = self.make_jsonrpc_request(
            f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
            {'message': revision, 'access_token': spreadsheet.access_token},
        )
        self.assertTrue(result['accepted'])
        self.assertEqual(spreadsheet.current_revision_uuid, revision['nextRevisionId'])

    @mute_logger('odoo.http')
    def test_dispatch_public_user_with_view_token_forbidden(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'view'})
        revision = self.new_revision_data(spreadsheet)
        with self.assertRaises(JsonRpcException, msg='odoo.exceptions.AccessError'):
            self.make_jsonrpc_request(
                f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
                {'message': revision, 'access_token': spreadsheet.access_token},
            )

    @mute_logger('odoo.http')
    def test_dispatch_public_user_snapshot_forbidden(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        snapshot_message = {
            'type': 'SNAPSHOT',
            'nextRevisionId': 'snapshot-id',
            'serverRevisionId': spreadsheet.current_revision_uuid,
            'data': {'revisionId': 'snapshot-id'},
        }
        with self.assertRaises(JsonRpcException, msg='odoo.exceptions.AccessError'):
            self.make_jsonrpc_request(
                f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
                {'message': snapshot_message, 'access_token': spreadsheet.access_token},
            )

    @mute_logger('odoo.http')
    def test_dispatch_public_user_blacklisted_command_forbidden(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        revision = self.new_revision_data(
            spreadsheet, commands=[{'type': 'ADD_PIVOT'}]
        )
        with self.assertRaises(JsonRpcException, msg='odoo.exceptions.AccessError'):
            self.make_jsonrpc_request(
                f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
                {'message': revision, 'access_token': spreadsheet.access_token},
            )

    def test_dispatch_public_user_undo_own_revision(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        revision = self.new_revision_data(spreadsheet)
        self.make_jsonrpc_request(
            f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
            {'message': revision, 'access_token': spreadsheet.access_token},
        )
        undo = {
            'type': 'REVISION_UNDONE',
            'undoneRevisionId': revision['nextRevisionId'],
            'nextRevisionId': 'undo-revision-id',
            'serverRevisionId': spreadsheet.current_revision_uuid,
        }
        result = self.make_jsonrpc_request(
            f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
            {'message': undo, 'access_token': spreadsheet.access_token},
        )
        self.assertTrue(result['accepted'])

    def test_dispatch_public_user_redo_own_revision(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        revision = self.new_revision_data(spreadsheet)
        self.make_jsonrpc_request(
            f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
            {'message': revision, 'access_token': spreadsheet.access_token},
        )
        redo = {
            'type': 'REVISION_REDONE',
            'redoneRevisionId': revision['nextRevisionId'],
            'nextRevisionId': 'redo-revision-id',
            'serverRevisionId': spreadsheet.current_revision_uuid,
        }
        result = self.make_jsonrpc_request(
            f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
            {'message': redo, 'access_token': spreadsheet.access_token},
        )
        self.assertTrue(result['accepted'])

    @mute_logger('odoo.http')
    def test_dispatch_public_user_cannot_undo_other_user_revision(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        # a revision created by another user (the internal owner)
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        other_revision_uuid = spreadsheet.current_revision_uuid
        undo = {
            'type': 'REVISION_UNDONE',
            'undoneRevisionId': other_revision_uuid,
            'nextRevisionId': 'undo-revision-id',
            'serverRevisionId': other_revision_uuid,
        }
        with self.assertRaises(JsonRpcException, msg='odoo.exceptions.AccessError'):
            self.make_jsonrpc_request(
                f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
                {'message': undo, 'access_token': spreadsheet.access_token},
            )

    @mute_logger('odoo.http')
    def test_dispatch_public_user_cannot_redo_other_user_revision(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        spreadsheet._dispatch_spreadsheet_message(self.new_revision_data(spreadsheet))
        other_revision_uuid = spreadsheet.current_revision_uuid
        redo = {
            'type': 'REVISION_REDONE',
            'redoneRevisionId': other_revision_uuid,
            'nextRevisionId': 'redo-revision-id',
            'serverRevisionId': other_revision_uuid,
        }
        with self.assertRaises(JsonRpcException, msg='odoo.exceptions.AccessError'):
            self.make_jsonrpc_request(
                f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
                {'message': redo, 'access_token': spreadsheet.access_token},
            )

    @mute_logger('odoo.http')
    def test_get_data_public_user_no_token(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'view'})
        response = self.url_open(
            f'/spreadsheet/data/documents.document/{spreadsheet.id}'
        )
        self.assertEqual(response.status_code, 403)

    @mute_logger('odoo.http')
    def test_get_data_public_user_wrong_token(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'view'})
        response = self.url_open(
            f'/spreadsheet/data/documents.document/{spreadsheet.id}/wrong-token'
        )
        self.assertEqual(response.status_code, 403)

    @mute_logger('odoo.http')
    def test_dispatch_public_user_no_token(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        revision = self.new_revision_data(spreadsheet)
        with self.assertRaises(JsonRpcException, msg='odoo.exceptions.AccessError'):
            self.make_jsonrpc_request(
                f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
                {'message': revision},
            )

    @mute_logger('odoo.http')
    def test_dispatch_public_user_wrong_token(self):
        spreadsheet = self.create_spreadsheet({'access_via_link': 'edit'})
        revision = self.new_revision_data(spreadsheet)
        with self.assertRaises(JsonRpcException, msg='odoo.exceptions.AccessError'):
            self.make_jsonrpc_request(
                f'/spreadsheet/documents.document/{spreadsheet.id}/dispatch',
                {'message': revision, 'access_token': 'wrong-token'},
            )
