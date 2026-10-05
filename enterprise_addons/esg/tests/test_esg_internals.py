from odoo.addons.esg.tests.esg_common import TestEsgCommon
from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import tagged, users


@tagged('mail_track')
class TestEsgTracking(TestEsgCommon, MailCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_employee.group_ids |= cls.env.ref('esg.esg_group_manager')

    @users('employee')
    def test_track_factor_line(self):
        """ Test tracking of factor line values on parent factor record """
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        self.flush_tracking()
        factor = self.emission_factor_computers_production.with_env(self.env)
        factor_lines = self.computers_production_gas_lines.with_env(self.env)

        with self.mock_mail_gateway(), self.mock_mail_app():
            factor_lines[:2].write({
                'activity_type_id': self.esg_activity_type.id,
                'gas_id': self.env.ref('esg.esg_gas_co2').id,
                'quantity': 200.8,
            })
            self.flush_tracking()
        # be independant of actual ordering of msg generation for asserts
        sorted_msg = self._new_msgs.sorted(lambda msg: (msg.model, msg.res_id, msg.body))
        # should have generated one message for each factor line on the factor
        # itself (aka: 2 * 2) (not on lines, which do not inherit from mail.thread)
        exp_generated_msg = [
            (factor, {  # recomputation of esg_emissions_values, real tracking compared to above which is manual
                'body': '',
                'message_type': 'tracking',
                'tracking_values': [
                    ('esg_emissions_value', 'float', 92.96, 404.25),
                ],
            }),
            (factor, {  # duplicate of second factor line changes, without esg computation
                'body': '<p>Updated values for Biogenic Methane (CH₄) (No activity type)</p>',
                'message_type': 'tracking',
                'tracking_values': [
                    ('activity_type_id', 'many2one', self.env['esg.activity.type'], self.esg_activity_type, {'html_string': 'Activity Type'}),
                    ('gas_id', 'many2one', self.env.ref('esg.esg_gas_ch4b'), self.env.ref('esg.esg_gas_co2'), {'html_string': 'Gas'}),
                    ('quantity', 'float', 0.02, 200.8, {'html_string': 'kg'}),
                ],
            }),
            (factor, {  # duplicate of first factor line changes, without esg computation
                'body': '<p>Updated values for Carbon Dioxide (CO₂) (No activity type)</p>',
                'message_type': 'tracking',
                'tracking_values': [
                    ('activity_type_id', 'many2one', self.env['esg.activity.type'], self.esg_activity_type, {'html_string': 'Activity Type'}),
                    ('quantity', 'float', 89.75, 200.8, {'html_string': 'kg'}),
                ],
            }),
        ]
        for message, (exp_record, exp_msg_values) in zip(sorted_msg, exp_generated_msg, strict=True):
            self.assertMessageFields(message, {
                'model': exp_record._name,
                'res_id': exp_record.id,
                **exp_msg_values,
            })
