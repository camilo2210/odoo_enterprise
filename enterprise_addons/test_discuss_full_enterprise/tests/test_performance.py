# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.test_discuss_full.tests.test_performance import TestDiscussFullPerformance

TestDiscussFullPerformance._query_count_init_store += 6
TestDiscussFullPerformance._query_count_init_messaging += 1
TestDiscussFullPerformance._query_count_messaging_menu_channels += 3

old_get_init_store_data_result = TestDiscussFullPerformance._get_init_store_data_result


def _get_init_store_data_result(self):
    res = old_get_init_store_data_result(self)
    channel_types_with_seen_infos = res["Store"]["channel_types_with_seen_infos"] + ["whatsapp"]
    res["Store"].update(
        {
            "channel_types_with_seen_infos": sorted(channel_types_with_seen_infos),
            "hasDocumentsUserGroup": False,
            "helpdesk_livechat_active": False,
            "has_access_create_ticket": False,
            "voipConfig": {
                "callActivityTypeId": self.env.ref("mail.mail_activity_data_call").id,
                "didNumber": None,
                "didNumberFormatted": None,
                "didNumberState": None,
                "mainNumber": None,
                "mainNumberFormatted": None,
                "buyCreditsUrl": None,
                "usesOdooProvider": False,
                "mode": "demo",
                "missedCalls": 0,
                "outboundCallerId": None,
                "outboundCallerIdFormatted": None,
                "outboundNumbers": [],
                "sharedOutboundNumbers": [],
                "isInternalCallingProvisioned": False,
                "pbxExtensionNumber": None,
                "pbxAddress": "localhost",
                "recordingPolicy": "disabled",
                "webSocketUrl": "ws://localhost",
                "voicemailCode": None,
                "transcriptionPolicy": "disabled",
            },
        }
    )
    res["res.users.settings"][0].update(
        {
            "do_not_disturb_until_dt": False,
            "external_device_number": False,
            "how_to_call_on_mobile": "ask",
            "should_call_from_another_device": False,
            "voip_secret": False,
            "voip_username": False,
        }
    )
    return res


TestDiscussFullPerformance._get_init_store_data_result = _get_init_store_data_result
