# Part of Odoo. See LICENSE file for full copyright and licensing details

from datetime import datetime
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo.addons.http_routing.tests.common import MockRequest
from odoo.tests import freeze_time

from .common import TestPlanningFieldServiceCommon


@freeze_time('2017-01-01 00:00:00')
class TestPlanningFieldServiceFlowWithGeolocation(TestPlanningFieldServiceCommon):
    def test_sign_in_with_geolocation(self):
        self.env['res.config.settings'].create({'group_field_service_allow_geolocation': True}).execute()
        intervention_with_george_user = self.intervention.with_user(self.george_user)
        geolocation_context = {
            "geolocation": {
                "success": True,
                "latitude": 10,
                "longitude": 13,
            }
        }

        with MockRequest(self.env, country_code="BE", city_name="Namur"):
            intervention_with_george_user.with_context(geolocation_context).action_sign_in()
        self.assertEqual(self.intervention.message_ids.sorted('create_date')[0].body, Markup('<p>GPS Coordinates: Namur, Belgium (10, 13) <a href="https://maps.google.com?q=10,13" target="_blank">View on Map</a></p>'))

    def test_sign_in_with_geolocation_with_denied_geolocation_permissions(self):
        self.env['res.config.settings'].create({'group_field_service_allow_geolocation': True}).execute()
        intervention_with_george_user = self.intervention.with_user(self.george_user)
        geolocation_context = {
            "geolocation": {
                "success": False,
                "message": "Location error: {Error returned by the browser, related to denied permission or maybe something else} e.g User denied Geolocation",
            }
        }

        with MockRequest(self.env, country_code="BE", city_name="Namur"):
            intervention_with_george_user.with_context(geolocation_context).action_sign_in()
        self.assertEqual(self.intervention.message_ids.sorted('create_date')[0].body, Markup('<p>Location error: {Error returned by the browser, related to denied permission or maybe something else} e.g User denied Geolocation</p>'))

    @freeze_time('2017-01-01 15:00:00')
    def test_update_resource_live_location(self):
        self.env['res.config.settings'].create({'group_field_service_allow_geolocation': False}).execute()
        george_resource = self.george_employee.resource_id

        result = self.env['res.users'].with_user(self.george_user).update_resource_live_location(10, 13)
        self.assertFalse(result, "Geolocation is disabled, so we should not track live location")
        self.assertRecordValues(george_resource, [{
            'live_latitude': False,
            'live_longitude': False,
            'live_location_last_update': False,
        }])

        self.env['res.config.settings'].create({'group_field_service_allow_geolocation': True}).execute()

        marcel_resource = self.marcel_employee.resource_id
        self.marcel_user.group_ids -= self.env.ref('planning.group_planning_user')
        result = self.env['res.users'].with_user(self.marcel_user).update_resource_live_location(10, 13)
        self.assertFalse(result, "Marcel is not a planning user, so we should not track live location")
        self.assertRecordValues(marcel_resource, [{
            'live_latitude': False,
            'live_longitude': False,
            'live_location_last_update': False,
        }])

        result = self.env['res.users'].with_user(self.george_user).update_resource_live_location(10, 13)
        self.assertFalse(result, "Live location should not be stored because last intervention is ended by more than one hour")
        self.assertRecordValues(george_resource, [{
            'live_latitude': False,
            'live_longitude': False,
            'live_location_last_update': False,
        }])

        self.env['planning.slot'].create([{
            'name': "Field Service 2",
            'partner_id': self.partner.id,
            'resource_ids': george_resource.ids,
            'start_datetime': datetime.now().replace(hour=13, minute=0, second=0),
            'end_datetime': datetime.now().replace(hour=16, minute=0, second=0),
        }])
        result = self.env['res.users'].with_user(self.george_user).update_resource_live_location(10, 13)
        self.assertTrue(result, "Live location should be stored because the technician hasn't finished his day")
        self.assertRecordValues(george_resource, [{
            'live_latitude': 10,
            'live_longitude': 13,
            'live_location_last_update': datetime.now(),
        }])

    @freeze_time('2017-01-01 15:00:00')
    def test_should_erase_live_location(self):
        result = self.env['res.users'].with_user(self.henri_user).should_erase_live_location()
        self.assertTrue(result, "Do not track user location because Henri has no shift assigned today")

        slot = self.env['planning.slot'].create([{
            'name': "Intervention past more than 1 hour ago",
            'partner_id': self.partner.id,
            'resource_ids': self.henri_employee.resource_id.ids,
            'start_datetime': datetime.now().replace(hour=8, minute=0, second=0),
            'end_datetime': datetime.now().replace(hour=12, minute=0, second=0),
        }])
        result = self.env['res.users'].with_user(self.henri_user).should_erase_live_location()
        self.assertTrue(result, "Do not track user location because Henri's last intervention of today is over since more than 1h")
        slot.unlink()

        slot = self.env['planning.slot'].create([{
            'name': "Intervention currently in progress",
            'partner_id': self.partner.id,
            'resource_ids': self.henri_employee.resource_id.ids,
            'start_datetime': datetime.now().replace(hour=14, minute=0, second=0),
            'end_datetime': datetime.now().replace(hour=16, minute=0, second=0),
        }])
        result = self.env['res.users'].with_user(self.henri_user).should_erase_live_location()
        self.assertFalse(result, "Track user location because Henri is currently on intervention")
        slot.unlink()

        slot = self.env['planning.slot'].create([{
            'name': "Intervention currently in progress",
            'partner_id': self.partner.id,
            'resource_ids': self.henri_employee.resource_id.ids,
            'start_datetime': datetime.now().replace(hour=16, minute=0, second=0),
            'end_datetime': datetime.now().replace(hour=17, minute=0, second=0),
        }])
        result = self.env['res.users'].with_user(self.henri_user).should_erase_live_location()
        self.assertFalse(result, "Track user location because Henri has an intervention later today")
        slot.unlink()

        slot = self.env['planning.slot'].create([{
            'name': "Multi-day intervention currently in progress",
            'partner_id': self.partner.id,
            'resource_ids': self.henri_employee.resource_id.ids,
            'start_datetime': datetime.now().replace(hour=8, minute=0, second=0) - relativedelta(days=1),
            'end_datetime': datetime.now().replace(hour=18, minute=0, second=0) + relativedelta(days=1),
        }])
        result = self.env['res.users'].with_user(self.henri_user).should_erase_live_location()
        self.assertFalse(result, "Track user location because Henri is currently on a multi-day intervention")
        slot.unlink()

    @freeze_time('2017-01-01 15:00:00')
    def test_cron_remove_outdated_live_location(self):
        self.marcel_employee.resource_id.write({
            'live_latitude': 10,
            'live_longitude': 13,
            'live_location_last_update': datetime.now().replace(hour=16, minute=4, second=48),
        })
        self.henri_employee.resource_id.write({
            'live_latitude': 12,
            'live_longitude': 16,
            'live_location_last_update': datetime.now().replace(hour=15, minute=18, second=57) - relativedelta(days=1),
        })
        self.george_employee.resource_id.write({
            'live_latitude': 18,
            'live_longitude': 21,
            'live_location_last_update': datetime.now().replace(hour=14, minute=58, second=26) - relativedelta(days=1),
        })
        self.env['resource.resource']._cron_remove_outdated_live_location()

        # The cron should preserve live locations if they do not date from more than one day ago
        self.assertRecordValues(self.marcel_employee.resource_id, [{
            'live_latitude': 10,
            'live_longitude': 13,
            'live_location_last_update': datetime.now().replace(hour=16, minute=4, second=48),
        }])
        self.assertRecordValues(self.henri_employee.resource_id, [{
            'live_latitude': 12,
            'live_longitude': 16,
            'live_location_last_update': (datetime.now().replace(hour=15, minute=18, second=57) - relativedelta(days=1)),
        }])
        # George's live location dates from more than one day, so it should be cleaned automatically
        self.assertRecordValues(self.george_employee.resource_id, [{
            'live_latitude': False,
            'live_longitude': False,
            'live_location_last_update': False,
        }])
