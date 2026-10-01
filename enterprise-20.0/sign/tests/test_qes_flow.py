# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from contextlib import contextmanager
from dateutil.relativedelta import relativedelta
from hashlib import sha256
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.sign.models import sign_request as sign_request_module
from odoo.addons.sign.models.sign_request_item import MAX_EXTERNAL_SIGNATURE_FAILURES
from odoo.addons.sign.tests.sign_controller_common import TestSignControllerCommon

SERVICE_URL = 'https://signing.host/'


@tagged('post_install', '-at_install')
class TestQesFlow(TestSignControllerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # a service brings its own auth method, and its roles sign the documents themselves
        auth_method = cls.env.registry['sign.item.role']._fields['auth_method']
        cls.classPatch(auth_method, '_selection', {**auth_method._selection, 'qes': 'Test Signing Service'})
        cls.qes_role = cls.env['sign.item.role'].create({
            'name': 'QES Role',
            'auth_method': 'qes',
        })
        cls.template_qes = cls.env['sign.template'].create({'name': 'template_qes'})
        cls.documents_qes = cls.env['sign.document'].create([
            {'attachment_id': attachment.id, 'template_id': cls.template_qes.id}
            for attachment in (cls.attachment, cls.attachment.copy({'name': 'annex.pdf'}))
        ])
        cls.env['sign.item'].create([
            {
                'type_id': cls.env.ref('sign.sign_item_type_text').id,
                'required': True,
                'responsible_id': cls.qes_role.id,
                'page': 1,
                'posX': 0.273, 'posY': 0.158, 'width': 0.150, 'height': 0.015,
                'document_id': document.id,
            }
            for document in cls.documents_qes
        ])

    @contextmanager
    def mock_host(self, **answers):
        """ Answers the routes sign calls on the signature host, and records the calls.

        :param answers: ``{route: answer}`` overriding what that route replies
        """
        self.host_calls = []
        answers = {
            'open': {'success': True, 'signing_url': SERVICE_URL, 'session_token': 'session1'},
            'resume': {'success': True, 'signing_url': SERVICE_URL, 'status': 'awaiting_approval'},
            'status': {'success': True, 'status': 'awaiting_approval'},
            'reject': {'success': True, 'status': 'expired'},
            **answers,
        }

        def host_call_mocked(item, route, **params):
            self.host_calls.append((route, params))
            return answers[route]

        def provider_mocked(role):
            return 'test' if role.auth_method == 'qes' else False

        def requires_external_signature_mocked(roles):
            for role in roles:
                role.requires_external_signature = role.auth_method == 'qes'

        with patch.object(self.env.registry['sign.item.role'],
                          '_compute_requires_external_signature', requires_external_signature_mocked), \
             patch.object(self.env.registry['sign.item.role'],
                          '_get_external_signature_provider', provider_mocked), \
             patch.object(self.env.registry['sign.request.item'], '_qes_host_call', host_call_mocked):
            yield

    def pdf_increment(self, document):
        frozen = bytes(document.frozen_file)
        previous_xref = int(frozen.rsplit(b'startxref', 1)[1].split()[0])
        return b'\n%%increment of document %d\nstartxref\n%d\n%%%%EOF\n' % (document.id, previous_xref)

    def signed_documents(self, request_item, selected_document=None):
        """ What the signing host returns once the request is signed: an increment per frozen document. """
        documents = []
        for document in request_item._get_documents_awaiting_external_signature():
            if selected_document is not None and document not in selected_document:
                continue
            increment = self.pdf_increment(document)
            documents.append({
                'document_id': document.id,
                'signature_increment': base64.b64encode(increment).decode(),
                'hash': sha256(bytes(document.frozen_file) + increment).hexdigest(),
            })
        return documents

    def create_qes_request(self):
        return self.env['sign.request'].create({
            'template_id': self.template_qes.id,
            'reference': self.template_qes.display_name,
            'request_item_ids': [Command.create({
                'partner_id': self.partner_1.id,
                'role_id': self.qes_role.id,
            })],
        })

    def url_open(self, *args, **kwargs):
        response = super().url_open(*args, **kwargs)
        self.env.invalidate_all()  # the request wrote through its own env
        return response

    def press_sign(self, sign_request, values=None):
        """ The signer fills their fields and presses Sign. """
        request_item = sign_request.request_item_ids
        response = self._json_url_open(
            '/sign/sign/%d/%s' % (sign_request.id, request_item.access_token),
            data={'signature': values if values is not None else self.create_sign_values(
                sign_request.template_id.sign_item_ids, self.qes_role.id)},
        ).json()['result']
        self.env.invalidate_all()
        return response

    def document_url(self, sign_request):
        return '/sign/document/%d/%s' % (sign_request.id, sign_request.request_item_ids.access_token)

    def test_pressing_sign_freezes_the_documents_and_hands_them_over(self):
        sign_request = self.create_qes_request()
        with self.mock_host():
            response = self.press_sign(sign_request)

        self.assertEqual(response['authorization_url'], SERVICE_URL)
        documents = sign_request.request_document_ids
        self.assertEqual(documents.mapped('state'), ['awaiting_signature'] * 2)
        self.assertEqual(
            sign_request.request_item_ids.external_signature_session_token, 'session1',
            "the session token the host opened should be set")

        route, params = self.host_calls[-1]
        self.assertEqual(route, 'open')
        self.assertEqual(len(params['documents']), 2)
        for document, sent in zip(documents, params['documents']):
            self.assertEqual(sent['document_id'], document.id)
            self.assertEqual(base64.b64decode(sent['file']), bytes(document.frozen_file))
            self.assertEqual(
                sent['hash'], sha256(bytes(document.frozen_file)).hexdigest(),
                "documents hash should be passed so the host can tell a document that did not arrive properly")

    def test_the_frozen_documents_carry_the_answers_being_signed(self):
        sign_request = self.create_qes_request()
        with self.mock_host():
            self.press_sign(sign_request)
        for document in sign_request.request_document_ids:
            self.assertTrue(
                bytes(document.frozen_file).startswith(bytes(document._get_file_bytes())) or
                len(bytes(document.frozen_file)) > len(bytes(document.file)),
                "the signer's own values are stamped on the bytes about to be signed")

    def test_a_service_that_refuses_is_surfaced_to_the_signer(self):
        sign_request = self.create_qes_request()
        with self.mock_host(open={'success': False, 'message': "No credits left."}):
            response = self.press_sign(sign_request)
        self.assertEqual(response, {'success': False, 'message': "No credits left."})
        self.assertEqual(
            sign_request.request_document_ids.mapped('state'), ['in_progress'] * 2,
            "documents are not left frozen on a session that was never opened")

    def test_opening_the_document_carries_on_where_the_signer_stopped(self):
        sign_request = self.create_qes_request()
        with self.mock_host():
            self.press_sign(sign_request)
            response = self.url_open(self.document_url(sign_request), allow_redirects=False)
        self.assertEqual(response.headers['Location'], SERVICE_URL)
        self.assertEqual(self.host_calls[-1][0], 'resume', "and asks for no new session")

    def test_opening_the_document_before_starting_an_external_signing_session(self):
        sign_request = self.create_qes_request()
        with self.mock_host():
            response = self.url_open(self.document_url(sign_request))
        self.assertEqual(response.status_code, 200, "the signer reads their document as usual")
        self.assertFalse(self.host_calls, "with no session of theirs, the host is not called")

    def test_collecting_completes_the_documents_and_the_signer(self):
        sign_request = self.create_qes_request()
        request_item = sign_request.request_item_ids
        with self.mock_host():
            self.press_sign(sign_request)
        frozen = {document: bytes(document.frozen_file) for document in sign_request.request_document_ids}

        with self.mock_host(status={
            'success': True, 'status': 'signed',
            'documents': self.signed_documents(request_item),
        }):
            self.url_open(self.document_url(sign_request), allow_redirects=False)

        for document, frozen_file in frozen.items():
            self.assertTrue(
                bytes(document.file).startswith(frozen_file),
                "a document is completed by appending to the bytes that were signed")
            self.assertFalse(document.frozen_file, "which are not kept once they are")
            self.assertIn(request_item, document.applied_item_ids)
        self.assertEqual(request_item.state, 'completed')
        self.assertEqual(sign_request.state, 'signed')

    def test_an_increment_that_did_not_survive_the_way_back(self):
        sign_request = self.create_qes_request()
        request_item = sign_request.request_item_ids
        with self.mock_host():
            self.press_sign(sign_request)

        documents = self.signed_documents(request_item)
        documents[1]['hash'] = sha256(b'something else entirely').hexdigest()
        with self.mock_host(status={'success': True, 'status': 'signed', 'documents': documents}), \
             mute_logger('odoo.addons.sign.models.sign_request_item'):
            request_item._sync_external_signature()

        self.assertEqual(
            sign_request.request_document_ids.mapped('state'), ['awaiting_signature'] * 2,
            "the documents are completed together or not at all")
        self.assertEqual(request_item.state, 'sent')
        self.assertEqual(
            request_item.external_signature_failures, 1,
            "one delivery that did not survive is counted, and the next attempt collects again")
        self.assertTrue(request_item.external_signature_session_token, "the session is kept")

    def test_a_signature_that_never_arrives_usable_is_given_up(self):
        sign_request = self.create_qes_request()
        request_item = sign_request.request_item_ids
        with self.mock_host():
            self.press_sign(sign_request)

        documents = self.signed_documents(request_item)
        documents[0]['hash'] = sha256(b'not what was collected').hexdigest()
        with self.mock_host(status={'success': True, 'status': 'signed', 'documents': documents}), \
             mute_logger('odoo.addons.sign.models.sign_request_item'):
            for _attempt in range(MAX_EXTERNAL_SIGNATURE_FAILURES):
                request_item._sync_external_signature()

        self.assertFalse(
            request_item.external_signature_session_token,
            "the service cannot tell its signature does not arrive whole, so this side stops asking")
        self.assertEqual(sign_request.request_document_ids.mapped('state'), ['in_progress'] * 2)
        self.assertEqual(
            request_item.external_signature_failures, 0,
            "The next session this signer opens should start with a cleared conuter")

    def test_a_delivery_that_is_missing_a_document(self):
        sign_request = self.create_qes_request()
        request_item = sign_request.request_item_ids
        with self.mock_host():
            self.press_sign(sign_request)

        documents = sign_request.request_document_ids
        with self.mock_host(status={
            'success': True, 'status': 'signed',
            'documents': self.signed_documents(request_item, selected_document=documents[0]),
        }), mute_logger('odoo.addons.sign.models.sign_request_item'):
            request_item._sync_external_signature()
        self.assertEqual(documents.mapped('state'), ['awaiting_signature'] * 2)
        self.assertEqual(request_item.state, 'sent')

        # the whole delivery arrives on a later attempt
        with self.mock_host(status={
            'success': True, 'status': 'signed',
            'documents': self.signed_documents(request_item),
        }):
            request_item._sync_external_signature()
        self.assertEqual(request_item.state, 'completed')
        self.assertEqual(sign_request.state, 'signed')

    def test_a_session_the_host_gave_up_lets_the_signer_start_again(self):
        sign_request = self.create_qes_request()
        request_item = sign_request.request_item_ids
        with self.mock_host():
            self.press_sign(sign_request)

        with self.mock_host(status={'success': True, 'status': 'expired'}):
            request_item._sync_external_signature()
        self.assertFalse(request_item.external_signature_session_token)
        self.assertEqual(
            sign_request.request_document_ids.mapped('state'), ['in_progress'] * 2, "the documents are let go of")

    def test_the_reminder_cron_collects_before_reminding(self):
        sign_request = self.create_qes_request()
        request_item = sign_request.request_item_ids
        with self.mock_host():
            self.press_sign(sign_request)
        sign_request.write({
            'reminder_enabled': True,
            'reminder': 1,
            'last_reminder': fields.Date.today() - relativedelta(days=2),
        })

        with self.mock_host(status={
            'success': True, 'status': 'signed',
            'documents': self.signed_documents(request_item),
        }):
            self.env['sign.request']._cron_reminder()

        # a signer who already signed is completed, not asked to sign again
        self.assertEqual(request_item.state, 'completed')
        self.assertEqual(sign_request.state, 'signed')

    def test_pressing_sign_again_unchanged_disturbs_nothing(self):
        sign_request = self.create_qes_request()
        documents = sign_request.request_document_ids
        with self.mock_host():
            self.press_sign(sign_request)
            frozen = [bytes(document.frozen_file) for document in documents]

            # the signer comes back to a page left open and presses Sign again
            response = self.press_sign(sign_request)

        self.assertEqual(response['authorization_url'], SERVICE_URL, "they carry on where they were")
        self.assertNotIn(
            'reject', [route for route, _params in self.host_calls],
            "nothing was given up, since what they submit is what is being signed")
        self.assertEqual(
            [bytes(document.frozen_file) for document in documents], frozen,
            "and the bytes their signature covers are not frozen a second time")

    def test_changing_an_answer_gives_the_attempt_up(self):
        sign_request = self.create_qes_request()
        request_item = sign_request.request_item_ids
        with self.mock_host():
            self.press_sign(sign_request)
            edited = dict.fromkeys(self.create_sign_values(
                sign_request.template_id.sign_item_ids, self.qes_role.id), 'edited after the freeze')
            self.press_sign(sign_request, values=edited)

        self.assertIn('reject', [route for route, _params in self.host_calls],
                      "the session covering the previous answers is given up")
        self.assertEqual(
            request_item.sign_item_value_ids.mapped('value'), ['edited after the freeze'] * 2,
            "and what they submit now is what the next attempt freezes")

    def test_a_signature_already_approved_outlives_a_late_change(self):
        sign_request = self.create_qes_request()
        request_item = sign_request.request_item_ids
        with self.mock_host():
            self.press_sign(sign_request)
            frozen_values = request_item.sign_item_value_ids.mapped('value')

            edited = dict.fromkeys(self.create_sign_values(
                sign_request.template_id.sign_item_ids, self.qes_role.id), 'too late')
            # the host keeps the session: the signer approved it already
            with self.mock_host(reject={'success': True, 'status': 'approved'}):
                response = self.press_sign(sign_request, values=edited)

        self.assertFalse(response['success'])
        self.assertIn('already approved', response['message'])
        self.assertEqual(
            request_item.sign_item_value_ids.mapped('value'), frozen_values,
            "the answers being signed are the ones they approved")
        self.assertEqual(sign_request.request_document_ids.mapped('state'), ['awaiting_signature'] * 2)

    def test_documents_too_large_to_be_signed_are_refused_to_be_sent(self):
        with self.mock_host(), \
             patch.object(sign_request_module, 'MAX_EXTERNAL_SIGNATURE_UPLOAD_SIZE', 1), \
             self.assertRaises(UserError):
            self.create_qes_request()

    def test_signing_order_is_forced(self):
        self.env['sign.item'].create({
            'type_id': self.env.ref('sign.sign_item_type_text').id,
            'required': True,
            'responsible_id': self.role_signer_1.id,
            'page': 1,
            'posX': 0.273, 'posY': 0.500, 'width': 0.150, 'height': 0.015,
            'document_id': self.documents_qes[0].id,
        })
        with self.mock_host():
            sign_request = self.env['sign.request'].create({
                'template_id': self.template_qes.id,
                'reference': self.template_qes.display_name,
                'request_item_ids': [Command.create({
                    'partner_id': self.partner_1.id,
                    'role_id': self.qes_role.id,
                }), Command.create({
                    'partner_id': self.partner_2.id,
                    'role_id': self.role_signer_1.id,
                })],
            })
            later_item = sign_request.request_item_ids.filtered(lambda item: item.role_id == self.role_signer_1)
            self.assertEqual(later_item.mail_sent_order, 2)

            with self.assertRaises(UserError):
                later_item.sign(self.create_sign_values(self.template_qes.sign_item_ids, self.role_signer_1.id))
