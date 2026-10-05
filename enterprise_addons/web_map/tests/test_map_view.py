from odoo.exceptions import ValidationError
from odoo.tools import mute_logger
from odoo.tests.common import tagged

from odoo.addons.base.tests.test_ir_ui_view import ViewCase


@tagged("at_install", "-post_install")
class TestMapView(ViewCase):
    def test_field_then_popover(self):
        self.assertValid(
            """
                <map res_partner="name">
                    <field name="name"/>
                    <popover>
                        <field name="email"/>
                    </popover>
                </map>
            """,
            model="res.partner",
        )

    def test_popover_then_field(self):
        self.assertValid(
            """
                <map res_partner="name">
                    <popover>
                        <field name="email"/>
                    </popover>
                    <field name="name"/>
                </map>
            """,
            model="res.partner",
        )

    def test_field_popover_field(self):
        self.assertValid(
            """
                <map res_partner="name">
                    <field name="name"/>
                    <popover>
                        <field name="email"/>
                    </popover>
                    <field name="city"/>
                </map>
            """,
            model="res.partner",
        )

    def test_popover_only(self):
        self.assertValid(
            """
                <map res_partner="name">
                    <popover>
                        <field name="email"/>
                    </popover>
                </map>
            """,
            model="res.partner",
        )

    def test_fields_only_no_popover(self):
        self.assertValid(
            """
                <map res_partner="name">
                    <field name="name"/>
                    <field name="city"/>
                </map>
            """,
            model="res.partner",
        )

    def test_field_without_string_is_valid(self):
        self.assertValid(
            """
                <map res_partner="name">
                    <field name="name"/>
                </map>
            """,
            model="res.partner",
        )

    def test_two_popovers_invalid(self):
        with (
            mute_logger("odoo.addons.web_map.validation"),
            mute_logger("odoo.tools.view_validation"),
        ):
            with self.assertRaises(ValidationError):
                self.View.create({
                    "arch": """
                        <map res_partner="name">
                            <popover>
                                <field name="email"/>
                            </popover>
                            <popover>
                                <field name="city"/>
                            </popover>
                        </map>
                    """,
                    "model": "res.partner",
                })
