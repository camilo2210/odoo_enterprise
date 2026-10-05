# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from datetime import date

from odoo.fields import Date
from odoo.tests import HttpCase, new_test_user, tagged

WARNINGS_URL = '/hr_payroll/dashboard/warnings'

# To keep a pretty indentation
MULTI_CARD_CODE = """
warning_multi_results = []
for day in (1, 2, 3):
    warning_multi_results.append({
        'name': 'Streamed Card %s' % day,
        'button_name': 'Review',
        'action': {'type': 'ir.actions.act_window', 'res_model': 'hr.employee'},
        'warning_date': date(2030, 1, day),
        'records': [],
    })
"""


@tagged('-at_install', 'post_install')
class TestPayrollWarningStream(HttpCase):
    """Tests of the dashboard warning stream: ``/hr_payroll/dashboard/warnings``.

    The route answers a NDJSON stream, one JSON payload per line, each card
    being written to the socket as soon as it is computed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Stream Company',
            'first_payrun_date': date(2025, 1, 1),
            'payroll_closing_date': '25',
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Eleven',
            'company_id': cls.company.id,
            'contract_date_start': date(2025, 1, 1),
            'structure_type_id': cls.env['hr.payroll.structure.type'].create({
                'name': 'Stream Monthly Structure Type',
                'default_schedule_pay': 'monthly',
                'country_id': False,
            }).id,
        })
        cls.payroll_user = new_test_user(
            cls.env, login='stream_payroll_user', password='stream_payroll_user',
            groups='base.group_user,hr_payroll.group_hr_payroll_user',
            company_id=cls.company.id,
        )
        # Snooze the warnings shipped with the modules, so that only the ones
        # created by a test are streamed.
        cls.env['hr.payroll.warning'].search([]).snooze_date = date.max

    def setUp(self):
        super().setUp()
        self.authenticate('stream_payroll_user', 'stream_payroll_user')

    def _create_warning(self, name, **values):
        """Create a warning matching ``self.employee``, hence yielding one card."""
        return self.env['hr.payroll.warning'].with_company(self.company).create({
            'name': name,
            'warning_type': 'domain',
            'model_id': self.env.ref('hr.model_hr_employee').id,
            'warning_domain': "[('id', '=', %d)]" % self.employee.id,
            'closing_on': 'next_payslip',
            'warning_color_class': 'warning',
            'button_name': 'Review Employee',
            **values,
        })

    def _stream_warnings(self):
        response = self.url_open(WARNINGS_URL, timeout=60)
        self.assertEqual(response.status_code, 200, response.text)
        return response, [json.loads(line) for line in response.text.splitlines() if line]

    def test_stream_card_and_headers(self):
        """A card is streamed for each applicable warning, then the done sentinel."""
        warning = self._create_warning('Streamed Warning')
        closing_date = self.company._get_monthly_payroll_next_closing_date()
        warning_date = warning._get_warning_date(self.employee, closing_date)

        response, payloads = self._stream_warnings()

        self.assertEqual(response.headers['Content-Type'], 'application/x-ndjson; charset=utf-8')
        self.assertEqual(response.headers['X-Accel-Buffering'], 'no', "proxies must not buffer the stream")
        self.assertEqual(response.headers.get('Transfer-Encoding'), 'chunked', "the body is sent chunk by chunk")
        self.assertNotIn('Content-Length', response.headers, "a streamed body has no known length")

        self.assertEqual([payload['type'] for payload in payloads], ['card', 'done'])
        card = payloads[0]['warning']
        self.assertEqual(card['key'], 'monthly_%s' % warning.id)
        self.assertEqual(card['name'], 'Streamed Warning')
        self.assertEqual(card['count'], 1)
        self.assertEqual(card['color_class'], 'warning')
        self.assertEqual(card['warning_date'], Date.to_string(warning_date))
        self.assertEqual(card['button_name'], 'Review Employee')
        self.assertEqual(card['button_action']['res_id'], self.employee.id)

    def test_stream_one_line_per_card(self):
        """A warning yielding several cards streams them one line at a time."""
        self._create_warning('Multi Card Warning', warning_type='python', evaluation_code=MULTI_CARD_CODE)

        _response, payloads = self._stream_warnings()

        self.assertEqual([payload['type'] for payload in payloads], ['card', 'card', 'card', 'done'])
        self.assertEqual(
            [payload['warning']['warning_date'] for payload in payloads[:-1]],
            ['2030-01-01', '2030-01-02', '2030-01-03'],
            "the cards of a single warning are streamed in the order they are computed",
        )

    def test_stream_error_card_does_not_abort_the_stream(self):
        """A warning that cannot be computed is streamed as an error card."""
        first = self._create_warning('First Warning', sequence=100)
        broken = self._create_warning(
            'Broken Warning', sequence=110,
            warning_type='python', evaluation_code='warning_records = undefined_variable',
        )
        last = self._create_warning('Last Warning', sequence=120)

        # The route logs the failure it recovers from, the ERROR log is expected.
        with self.assertLogs('odoo.addons.hr_payroll.controllers.main', level='ERROR') as capture:
            _response, payloads = self._stream_warnings()
        self.assertIn(
            'Could not compute payroll dashboard warning %s: %s' % (broken.id, broken.name),
            capture.output[0],
        )

        self.assertEqual([payload['type'] for payload in payloads], ['card', 'card', 'card', 'done'])
        self.assertEqual(
            [payload['warning']['key'] for payload in payloads[:-1]],
            ['monthly_%s' % first.id, 'error_%s' % broken.id, 'monthly_%s' % last.id],
            "a failing warning neither aborts the stream nor drops the following warnings",
        )

        error_card = payloads[1]['warning']
        self.assertEqual(error_card['name'], 'Broken Warning')
        self.assertEqual(error_card['color_class'], 'danger')
        self.assertEqual(error_card['button_action']['tag'], 'display_exception')
        self.assertEqual(error_card['button_action']['params']['data']['name'], 'odoo.exceptions.UserError')

    def test_stream_hostile_warning_is_not_executable(self):
        """A hostile warning cannot get its payload run by the browser.

        The name of a warning is user input, and it lands verbatim in the body
        as ``json.dumps`` does not escape HTML. Opening the route in a browser
        must not run it: the content type is not renderable and, thanks to
        ``nosniff``, cannot be sniffed as ``text/html`` either.
        """
        self._create_warning("<script>alert('xss')</script>")

        response, payloads = self._stream_warnings()

        self.assertEqual(response.headers['Content-Type'], 'application/x-ndjson; charset=utf-8')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(
            payloads[0]['warning']['name'], "<script>alert('xss')</script>",
            "the name is streamed as inert data, escaping is up to the client",
        )

    def test_stream_hostile_warning_cannot_forge_a_line(self):
        """A hostile warning cannot inject a payload in the NDJSON stream.

        Lines are the framing of the protocol: a name holding newlines must
        neither add a forged card nor end the stream early with a fake sentinel.
        """
        forged = '{"type": "card", "warning": {"key": "forged_card"}}'
        warning = self._create_warning('Hostile Warning\n%s\n{"type": "done"}' % forged)

        response = self.url_open(WARNINGS_URL, timeout=60)

        self.assertEqual(response.status_code, 200)
        lines = response.text.splitlines()
        self.assertEqual(len(lines), 2, "the newlines of the name must not split the payload")
        payloads = [json.loads(line) for line in lines]
        self.assertEqual([payload['type'] for payload in payloads], ['card', 'done'])
        self.assertEqual(payloads[0]['warning']['name'], warning.name)

    def test_stream_requires_the_payroll_group(self):
        """Only payroll users may stream the dashboard warnings."""
        self._create_warning('Streamed Warning')
        new_test_user(
            self.env, login='stream_basic_user', password='stream_basic_user',
            groups='base.group_user', company_id=self.company.id,
        )
        self.authenticate('stream_basic_user', 'stream_basic_user')

        response = self.url_open(WARNINGS_URL, timeout=60)

        self.assertEqual(response.status_code, 403)
