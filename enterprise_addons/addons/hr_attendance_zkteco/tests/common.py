from unittest.mock import MagicMock, patch

from odoo.tests import new_test_user
from odoo.tests.common import TransactionCase

SESSION_PATH = "odoo.addons.hr_attendance_zkteco.models.res_company.ResCompany._get_zkteco_session"


class ZktecoCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "zkteco_server_url": "https://biotime.test",
                "zkteco_email": "biotime@example.com",
                "zkteco_password": "secret",
                "zkteco_company": "Test BioTime",
                "zkteco_initial_sync_done": True,
                "zkteco_transaction_fetch_days": 2,
                "zkteco_checkout_lookback_days": 2,
            }
        )
        cls.terminal = cls.env["zkteco.terminal"].create(
            {
                "name": "Front Door",
                "terminal_sn": "SN-001",
                "company_id": cls.company.id,
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Bilal El Khattab",
                "zkteco_emp_id": "EMP-1",
                "tz": "Europe/Brussels",
                "company_id": cls.company.id,
            }
        )
        cls.manager = new_test_user(
            cls.env,
            login="zk_manager",
            groups="base.group_system,hr_attendance.group_hr_attendance_manager,hr.group_hr_user",
            company_id=cls.company.id,
        )
        cls.basic_user = new_test_user(
            cls.env,
            login="zk_basic",
            groups="hr_attendance.group_hr_attendance_user",
            company_id=cls.company.id,
        )

    def _punch_payload(self, txid, *, emp_code="EMP-1", punch_state="0", punch_time="2024-01-15 09:00:00", terminal_sn="SN-001"):
        return {
            "id": txid,
            "emp_code": emp_code,
            "punch_state": punch_state,
            "punch_time": punch_time,
            "terminal_sn": terminal_sn,
        }

    def _mock_session(self, *, transactions=(), terminals=(), single=None):
        """Stand-in for the ``requests.Session`` that ``_get_zkteco_session`` returns.

        Only the network transport is faked: ``session.get`` is routed by URL to the
        right canned BioTime payload, so the real pagination in
        ``utils._get_records_from_server`` and the single-record re-fetch both run their
        actual code paths. Everything past the HTTP boundary is real Odoo logic.
        """
        session = MagicMock()
        session.base_url = "https://biotime.test"

        def _get(url, params=None, timeout=None):
            response = MagicMock()
            response.raise_for_status.return_value = None
            if url.endswith("/terminals/"):
                response.json.return_value = {"data": list(terminals), "next": None}
            elif url.rstrip("/").rsplit("/", 1)[-1].isdigit():  # /iclock/api/transactions/<id>/
                response.json.return_value = single or {}
            else:
                response.json.return_value = {"data": list(transactions), "next": None}
            return response

        session.get.side_effect = _get
        return session

    def _mock_zkteco(self, **responses):
        return patch(SESSION_PATH, return_value=self._mock_session(**responses))
