import json
from copy import deepcopy

from lxml import etree

import odoo
from odoo import api
from odoo.http import request_var
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from odoo.tools import DotDict

from odoo.addons.web_studio.controllers.main import WebStudioController


class TestStudioController(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env = api.Environment(self.cr, odoo.SUPERUSER_ID, {'load_all_views': True})
        request_reset = request_var.set(self)
        self.addCleanup(request_var.reset, request_reset)
        self.session = DotDict({'debug': ''})
        self.studio_controller = WebStudioController()

    def _transform_arch_for_assert(self, arch_string):
        parser = etree.XMLParser(remove_blank_text=True)
        arch_string = etree.fromstring(arch_string, parser=parser)
        return etree.tostring(arch_string, pretty_print=True, encoding='unicode')

    def assertViewArchEqual(self, original, expected):
        if original:
            original = self._transform_arch_for_assert(original)
        if expected:
            expected = self._transform_arch_for_assert(expected)
        self.assertEqual(original, expected)

    def update_context(self, **overrides):
        self.env = self.env(context=dict(self.env.context, **overrides))


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestEditView(TestStudioController):

    def edit_view(self, base_view, studio_arch="", operations=None, model=None, context=None):
        _ops = None
        if isinstance(operations, list):
            _ops = []
            for op in operations:
                _ops.append(deepcopy(op))  # the edit view controller may alter objects in place
        if studio_arch == "":
            studio_arch = "<data/>"
        return self.studio_controller.edit_view(base_view.id, studio_arch, _ops, model, context)

    def test_edit_view_binary_and_attribute(self):
        base_view = self.env['ir.ui.view'].create({
            'name': 'TestForm',
            'type': 'form',
            'model': 'res.partner',
            'arch': """
                <form>
                    <field name="display_name" />
                </form>"""
        })

        add_binary_op = {
            'type': 'add',
            'target': {'tag': 'field',
                       'attrs': {'name': 'display_name'},
                       'xpath_info': [{'tag': 'form', 'indice': 1},
                                      {'tag': 'field', 'indice': 1}]},
            'position': 'after',
            'node': {'tag': 'field',
                     'attrs': {},
                     'field_description': {'type': 'binary',
                                           'field_description': 'New File',
                                           'name': 'x_studio_binary_field_WocAO',
                                           'model_name': 'res.partner'}}
        }

        self.edit_view(base_view, operations=[add_binary_op])
        self.assertViewArchEqual(
            base_view.get_combined_arch(),
            """
              <form>
                <field name="display_name"/>
                <field filename="x_studio_binary_field_WocAO_filename" name="x_studio_binary_field_WocAO"/>
                <field invisible="True" name="x_studio_binary_field_WocAO_filename"/>
              </form>
            """
        )

        add_widget_op = {
            'type': 'attributes',
            'target': {'tag': 'field',
                       'attrs': {'name': 'x_studio_binary_field_WocAO'},
                       'xpath_info': [{'tag': 'form', 'indice': 1},
                                      {'tag': 'field', 'indice': 2}]},
            'position': 'attributes',
            'node': {'tag': 'field',
                     'attrs': {'filename': 'x_studio_binary_field_WocAO_filename',
                               'name': 'x_studio_binary_field_WocAO',
                               'id': 'x_studio_binary_field_WocAO'},
                     'children': [],
                     'has_label': True},
            'new_attrs': {'widget': 'pdf_viewer', 'options': ''}
        }

        ops = [
            add_binary_op,
            add_widget_op
        ]
        self.edit_view(base_view, operations=ops)
        self.assertViewArchEqual(
            base_view.get_combined_arch(),
            """
              <form>
                <field name="display_name"/>
                <field filename="x_studio_binary_field_WocAO_filename" name="x_studio_binary_field_WocAO" widget="pdf_viewer"/>
                <field invisible="True" name="x_studio_binary_field_WocAO_filename"/>
              </form>
            """
        )

    def test_edit_view_binary_and_attribute_then_remove_binary(self):
        base_view = self.env['ir.ui.view'].create({
            'name': 'TestForm',
            'type': 'form',
            'model': 'res.partner',
            'arch': """
                <form>
                    <field name="display_name" />
                </form>"""
        })

        add_binary_op = {
            'type': 'add',
            'target': {'tag': 'field',
                       'attrs': {'name': 'display_name'},
                       'xpath_info': [{'tag': 'form', 'indice': 1},
                                      {'tag': 'field', 'indice': 1}]},
            'position': 'after',
            'node': {'tag': 'field',
                     'attrs': {},
                     'field_description': {'type': 'binary',
                                           'field_description': 'New File',
                                           'name': 'x_studio_binary_field_WocAO',
                                           'model_name': 'res.partner'}}
        }

        self.edit_view(base_view, operations=[add_binary_op])

        add_widget_op = {
            'type': 'attributes',
            'target': {'tag': 'field',
                       'attrs': {'name': 'x_studio_binary_field_WocAO'},
                       'xpath_info': [{'tag': 'form', 'indice': 1},
                                      {'tag': 'field', 'indice': 2}]},
            'position': 'attributes',
            'node': {'tag': 'field',
                     'attrs': {'filename': 'x_studio_binary_field_WocAO_filename',
                               'name': 'x_studio_binary_field_WocAO',
                               'id': 'x_studio_binary_field_WocAO'},
                     'children': [],
                     'has_label': True},
            'new_attrs': {'widget': 'pdf_viewer', 'options': ''}
        }

        ops = [
            add_binary_op,
            add_widget_op
        ]
        self.edit_view(base_view, operations=ops)

        remove_binary_op = {
            'type': 'remove',
            'target': {'tag': 'field',
                       'attrs': {'name': 'x_studio_binary_field_WocAO'},
                       'xpath_info': [{'tag': 'form', 'indice': 1},
                                      {'tag': 'field', 'indice': 2}]},
        }
        self.edit_view(base_view, operations=ops + [remove_binary_op])
        # The filename field is still present in the view
        # this is not intentional rather, it is way easier to leave this invisible field there
        self.assertViewArchEqual(
            base_view.get_combined_arch(),
            """
              <form>
                <field name="display_name"/>
                <field invisible="True" name="x_studio_binary_field_WocAO_filename"/>
              </form>
            """
        )

    def test_edit_view_options_attribute(self):
        op = {
            'type': 'attributes',
            'target': {
                'tag': 'field',
                'attrs': {'name': 'group_ids'},
                'xpath_info': [
                    {'tag': 'form', 'indice': 1},
                    {'tag': 'sheet', 'indice': 1},
                    {'tag': 'field', 'indice': 2}
                ],
                'subview_xpath': "//field[@name='user_ids']/form[2]"
            },
            'position': 'attributes',
            'node': {
                'tag': 'field',
                'attrs': {
                    'name': 'group_ids',
                    'widget': 'many2many_tags',
                    'options': "{'color_field': 'color', 'on_tag_click': 'edit_color'}",
                },
                'children': [],
                'has_label': True
            },
            'new_attrs': {'options': '{"color_field":"color","no_create":true}'}
        }

        base_view = self.env['ir.ui.view'].create({
            'name': 'TestForm',
            'type': 'form',
            'model': 'res.partner',
            'arch': """
                    <form>
                        <sheet>
                            <field name="display_name"/>
                            <field name="user_ids">
                                <form />
                                <form>
                                    <sheet>
                                        <field name="display_name" />
                                        <field name="group_ids" widget='many2many_tags' options="{'color_field': 'color', 'on_tag_click': 'edit_color'}"/>
                                    </sheet>
                                </form>
                            </field>
                        </sheet>
                    </form>"""
        })
        self.edit_view(base_view, operations=[op], model='res.users')

        self.assertViewArchEqual(
            base_view.get_combined_arch(),
            """
                <form>
                    <sheet>
                        <field name="display_name"/>
                        <field name="user_ids">
                            <form />
                            <form>
                                <sheet>
                                    <field name="display_name"/>
                                    <field name="group_ids" widget="many2many_tags" options="{&quot;color_field&quot;:&quot;color&quot;,&quot;no_create&quot;:true}"/>
                                </sheet>
                            </form>
                        </field>
                    </sheet>
                </form>
            """
        )

    def test_edit_view_create_attribute_attribute(self):
        op = {
            'type': 'attributes',
            'target': {
                'tag': 'kanban',
                'attrs': {},
                'xpath_info': [
                    {'tag': 'kanban', 'indice': 1},
                ],
                'isSubviewAttr': True,
            },
            'position': 'attributes',
            'new_attrs': {'create': True}
        }

        base_view = self.env['ir.ui.view'].create({
            'name': 'TestKanban',
            'type': 'kanban',
            'model': 'res.partner',
            'arch': """
                <kanban>
                    <templates><t t-name="card" /></templates>
                </kanban>
            """
        })
        self.edit_view(base_view, operations=[op], model='res.users')

        self.assertViewArchEqual(
            base_view.get_combined_arch(),
            """
                <kanban create="true">
                    <templates><t t-name="card" /></templates>
                </kanban>
            """
        )

    def test_edit_view_remove_attribute(self):
        op = {
            'type': 'attributes',
            'target': {
                'tag': 'calendar',
                'attrs': {},
                'xpath_info': [
                    {'tag': 'calendar', 'indice': 1},
                ],
            },
            'position': 'attributes',
            'new_attrs': {'date_stop': None}
        }

        base_view = self.env['ir.ui.view'].create({
            'name': 'TestKanban',
            'type': 'calendar',
            'model': 'res.partner',
            'arch': """
                <calendar date_start="create_date" date_stop="write_date">
                    <field name="display_name" />
                </calendar>
            """
        })
        self.edit_view(base_view, operations=[op])

        self.assertViewArchEqual(
            base_view.get_combined_arch(),
            """
                <calendar date_start="create_date">
                    <field name="display_name" />
                </calendar>
            """
        )

    def test_edit_view_add_binary_field_inside_group(self):
        arch = """<form>
            <sheet>
                <notebook>
                    <page>
                        <group>
                            <group name="group_left" />
                            <group name="group_right" />
                        </group>
                    </page>
                </notebook>
            </sheet>
        </form>"""

        base_view = self.env['ir.ui.view'].create({
            'name': 'TestForm',
            'type': 'form',
            'model': 'res.partner',
            'arch': arch
        })

        operation = {
            'type': 'add',
            'target': {
                'tag': 'group',
                'attrs': {
                    'name': 'group_left'
                },
                'xpath_info': [
                    {'tag': 'form', 'indice': 1},
                    {'tag': 'sheet', 'indice': 1},
                    {'tag': 'notebook', 'indice': 1},
                    {'tag': 'page', 'indice': 1},
                    {'tag': 'group', 'indice': 1},
                    {'tag': 'group', 'indice': 1}
                ]
            },
            'position': 'inside',
            'node': {
                'tag': 'field',
                'attrs': {},
                'field_description': {
                    'type': 'binary',
                    'field_description': 'New File',
                    'name': 'x_studio_field_fDthx',
                    'model_name': 'res.partner'
                }

            }
        }

        self.edit_view(base_view, operations=[operation])

        expected_arch = """<form>
            <sheet>
                <notebook>
                    <page>
                        <group>
                            <group name="group_left">
                                <field filename="x_studio_field_fDthx_filename" name="x_studio_field_fDthx"/>
                                <field invisible="True" name="x_studio_field_fDthx_filename"/>
                            </group>
                            <group name="group_right"/>
                        </group>
                    </page>
                </notebook>
            </sheet>
        </form>"""

        self.assertViewArchEqual(base_view.get_combined_arch(), expected_arch)

    def test_edit_attribute_studio_groups(self):
        """ Tests the behavior of setting the attribute `studio_groups` on field view nodes having a `groups=` attribute
        A second goal is to test the behavior of a field node having a `groups=` attribute set on the node
        and another `groups=` on the field definition in the model.
        e.g.
        `code = fields.Text(string='Python Code', groups='base.group_system',`
        `<field name="code" groups="base.group_multi_currency"/>`
        For this above case, a temporary technical node is created during the view postprocessing,
        wrapping the `<field groups="..."` node,
        to simulate a AND between the two groups: you must have BOTH groups in order to see the given field node,
        and the technical node should not remain in the end.
        """
        # Ensure there is a group on the `code` field, as the goal of this test is to test the behavior
        # of a field having a group in the model definition in addition to another group on the field node in the view.
        self.assertEqual(self.env['ir.actions.server']._fields['code'].groups, 'base.group_system')
        view = self.env['ir.ui.view'].create({
            'name': 'foo',
            'type': 'list',
            'model': 'ir.actions.server',
            'arch': """
                <list>
                    <field name="name"/>
                    <field name="state" groups="base.group_multi_currency"/>
                    <field name="code" groups="base.group_multi_currency"/>
                </list>"""
        })
        with self.debug_mode():
            arch = self.env['ir.actions.server'].with_context(studio=True).get_view(view.id)['arch']
            tree = etree.fromstring(arch)
            children = list(tree.iterdescendants())
            self.assertEqual(len(children), 3, 'The list view must have only 3 descendants in total, the 3 fields')
            name, state, code = children
            self.assertFalse(name.get('studio_groups'))
            self.assertTrue(state.get('studio_groups'))
            self.assertTrue(code.get('studio_groups'))
            for node in (state, code):
                self.assertEqual(json.loads(node.get('studio_groups'))[0]['name'], 'Multi Currencies')

    def test_edit_field_present_in_multiple_views(self):
        """ a use case where the hack before this fix doesn't work.
        We try to edit a field that is present in two views, and studio
        must modify the field in the correct view and do not confuse it
        with the other one.
        """
        IrModelFields = self.env["ir.model.fields"].with_context(studio=True)
        source_model = self.env["ir.model"].search([("model", "=", "res.partner")])
        destination_model = self.env["ir.model"].search(
            [("model", "=", "res.currency")]
        )
        IrModelFields.create(
            {
                "ttype": "many2many",
                "model_id": source_model.id,
                "relation": destination_model.model,
                "name": "x_test_field_x",
                "relation_table": IrModelFields._get_next_relation(
                    source_model.model, destination_model.model
                ),
            }
        )
        arch = """ <form>
            <field name="user_ids">
                <form>
                    <field name="x_test_field_x"/>
                </form>
                <list>
                    <field name="x_test_field_x"/>
                </list>
            </field>
        </form>"""

        base_view = self.env['ir.ui.view'].create({
            'name': 'TestForm',
            'type': 'form',
            'model': 'res.partner',
            'arch': arch
        })

        operation = {
            'type': 'attributes',
            'target': {
                'tag': 'field',
                    'attrs': {
                        'name': 'x_test_field_x'
                    },
                    'xpath_info': [
                        {'tag': 'list', 'indice': 1},
                        {'tag': 'field', 'indice': 1}
                    ],
                    'subview_xpath': "//field[@name='user_ids']/list"
                },
                'position': 'attributes',
                'node': {
                    'tag': 'field',
                    'attrs': {
                        'name': 'x_test_field_x',
                        'id': 'x_test_field_x'
                    },
                },
                'new_attrs': {
                    'options': "{\"no_create\": true}"
                }
            }

        self.edit_view(base_view, operations=[operation])

        expected_arch = """ <form>
            <field name="user_ids">
                <form>
                    <field name="x_test_field_x"/>
                </form>
                <list>
                    <field name="x_test_field_x" options="{&quot;no_create&quot;: true}"/>
                </list>
            </field>
        </form>"""
        self.assertViewArchEqual(base_view.get_combined_arch(), expected_arch)

    def test_edit_view_unlocatable_target_raises_validation_error(self):
        """ The client may send an operation whose target xpath doesn't match
        anything in the actual stored arch.

        `normalize()` must not let the resulting ValueError escape as a raw,
        unhandled exception: it has to be a ValidationError, like any other
        unlocatable studio spec, so that `edit_view()` can fall back to the
        un-optimized arch instead of crashing with a traceback.
        """
        base_view = self.env['ir.ui.view'].create({
            'name': 'TestForm',
            'type': 'form',
            'model': 'res.partner',
            'arch': """
                <form>
                    <div>
                        <field name="display_name"/>
                    </div>
                </form>""",
        })

        # There is only one <field/> inside the <div/>: this targets a
        # second one that doesn't exist, the same situation as a client
        # xpath computed against a field the server doesn't statically have.
        operation = {
            'type': 'attributes',
            'target': {
                'tag': 'field',
                'attrs': {'name': 'display_name'},
                'xpath_info': [
                    {'tag': 'form', 'indice': 1},
                    {'tag': 'div', 'indice': 1},
                    {'tag': 'field', 'indice': 2},
                ],
            },
            'position': 'attributes',
            'node': {'tag': 'field', 'attrs': {'name': 'display_name'}},
            'new_attrs': {'invisible': 'False'},
        }

        with self.assertRaises(ValidationError):
            self.edit_view(base_view, operations=[operation])

    def test_edit_attribute_studio_groups_tree_column_invisible(self):
        test_group = self.env['res.groups'].create({'name': 'test_group'})
        self.env['ir.model.data'].create({
            'module': 'base',
            'name': 'test_group',
            'model': 'res.groups',
            'res_id': test_group.id,
        })
        for view_type, arch, expected_modifiers in [
            ('list', """
                <list>
                    <field name="name" groups="base.test_group"/>
                </list>
            """, {'column_invisible': 'True', 'invisible': None}),
            ('list', """
                <list>
                    <header>
                        <button name="name" groups="base.test_group"/>
                    </header>
                </list>
            """, {'invisible': 'True', 'column_invisible': None}),
            ('form', """
                <form>
                    <field name="child_ids">
                        <list>
                            <field name="name" groups="base.test_group"/>
                        </list>
                    </field>
                </form>
            """, {'column_invisible': 'True', 'invisible': None}),
            ('list', """
                <list>
                    <field name="child_ids">
                        <form>
                            <field name="name" groups="base.test_group"/>
                        </form>
                    </field>
                </list>
            """, {'invisible': 'True', 'column_invisible': None}),
        ]:
            view = self.env['ir.ui.view'].create({
                'name': 'foo',
                'type': view_type,
                'model': 'res.partner',
                'arch': arch,
            })
            arch = self.env['res.partner'].with_context(studio=True).get_view(view.id)['arch']
            tree = etree.fromstring(arch)
            node = tree.xpath('//*[@name="name"]')[0]
            for modifier, value in expected_modifiers.items():
                self.assertEqual(node.get(modifier), value)

    def test_get_view_t_groups(self):
        """Tests the behavior of <t groups="..."></t> blocks with Studio."""
        test_group = self.env['res.groups'].create({'name': 'test_group'})
        self.env['ir.model.data'].create({
            'module': 'base',
            'name': 'test_group',
            'model': 'res.groups',
            'res_id': test_group.id,
        })
        for view_type, arch, expected_modifiers in [
            # The user has the group of the `<t>` node, the `<t>` node **must remain**, and be visible.
            ('form', """
                <form>
                    <t groups="base.group_user">
                        <field name="name"/>
                    </t>
                </form>
            """, {'invisible': None}),
            # The user doesn't have the group of the `<t>` node, the `<t>` node **must remain**, and be invisible.
            ('form', """
                <form>
                    <t groups="base.test_group">
                        <field name="name"/>
                    </t>
                </form>
            """, {'invisible': 'True'}),
        ]:
            view = self.env['ir.ui.view'].create({
                'name': 'foo',
                'type': view_type,
                'model': 'res.partner',
                'arch': arch,
            })
            arch = self.env['res.partner'].with_context(studio=True).get_view(view.id)['arch']
            tree = etree.fromstring(arch)
            self.assertTrue(tree.xpath('//t'))
            node = tree.xpath('//t')[0]
            for modifier, value in expected_modifiers.items():
                self.assertEqual(node.get(modifier), value)

    def test_open_users_form_with_studio(self):
        """Tests the res.users form view can be loaded with Studio.

        The res.users form is an edge case, because it uses fake fields in its view, which do not exist in the model.
        Make sure the Studio overrides regarding the loading of the views, including the postprocessing,
        are able to handle these non-existing fields.
        """
        arch = self.env['res.users'].with_context(studio=True).get_view(self.env.ref('base.view_users_form').id)['arch']
        self.assertTrue(arch)

    def test_add_many2one_with_custom_rec_name(self):
        base_view = self.env['ir.ui.view'].create({
            'name': 'TestForm',
            'type': 'form',
            'model': 'res.partner',
            'arch': """
                    <form>
                        <field name="display_name" />
                    </form>"""
        })

        relation_id = self.env['ir.model'].search([["model", "=", "res.partner.bank"]]).id

        add_many2one_field_op = {
            "type": "add",
            "target": {
                "tag": "field",
                "attrs": {"name": "display_name"},
                "xpath_info": [
                    {"tag": "form", "indice": 1},
                    {"tag": "field", "indice": 1},
                ],
            },
            "position": "after",
            "node": {
                "tag": "field",
                "attrs": {},
                "field_description": {
                    "type": "many2one",
                    "field_description": "ddd",
                    "special": False,
                    "name": "x_studio_many2one_field_sNT7g",
                    "model_name": "res.partner",
                    "relation_id": relation_id,
                },
            },
        }

        self.edit_view(base_view, operations=[add_many2one_field_op])
        self.assertViewArchEqual(
            base_view.get_combined_arch(),
            """
              <form>
                <field name="display_name" />
                <field name="x_studio_many2one_field_sNT7g" options="{'create_name_field': 'account_number'}"/>
              </form>
            """
        )

    def test_edit_inherited_view(self):
        # accidentally pass the id of extension view instead of the primary
        main = self.env["ir.ui.view"].create({
            "name": "test",
            "model": "res.partner",
            "type": "list",
            "arch": """<list><field name="display_name" /></list>"""
        })
        inherit = self.env["ir.ui.view"].create({
            "name": "test",
            "mode": "extension",
            "inherit_id": main.id,
            "model": "res.partner",
            "type": "list",
            "arch": """<xpath position="after" expr="//field[@name='display_name']">
                <field name="function" />
                </xpath>
            """
        })
        op = {
            'type': 'add',
            'node': {
                'tag': 'field',
                'attrs': {
                    'name': 'name'
                }
            },
            'target': {
                'tag': 'field',
                'attrs': {},
                'xpath_info': [
                    {'tag': 'list', 'indice': 1},
                    {'tag': 'field', 'indice': 2}
                ],
            },
            'position': 'after',
        }
        res = self.edit_view(inherit, "", [op])
        studio_view_id = self.env["ir.ui.view"].browse(res["studio_view_id"])
        self.assertEqual(studio_view_id.inherit_id, main)
        self.assertViewArchEqual(studio_view_id.arch, """
        <data>
          <xpath expr="/list//field[@name='function']" position="after">
            <field name="name"/>
          </xpath>
        </data>
        """)

    def test_edit_kanban_with_card_view(self):
        card_view = self.env["ir.ui.view"].create({
            "name": "test.card",
            "model": "res.partner",
            "type": "card",
            "arch": """
                <card>
                    <templates>
                        <t t-name="card">
                            <field name="display_name"/>
                        </t>
                    </templates>
                </card>
            """,
        })
        self.env["ir.ui.view"].create({
            "name": "test.card.extension",
            "model": "res.partner",
            "type": "card",
            "inherit_id": card_view.id,
            "arch": """
                <field name="display_name" position="after">
                    <field name="email"/>
                </field>
            """,
        })
        kanban_view = self.env["ir.ui.view"].create({
            "name": "test.kanban",
            "model": "res.partner",
            "type": "kanban",
            "arch": f'<kanban card_id="{card_view.id}"/>',
        })
        inherited_kanban_view = self.env["ir.ui.view"].create({
            "name": "test.kanban.primary",
            "model": "res.partner",
            "type": "kanban",
            "inherit_id": kanban_view.id,
            "mode": "primary",
            "arch": """
                <kanban position="attributes">
                    <attribute name="default_group_by">country_id</attribute>
                </kanban>
            """,
        })
        target = {
            "tag": "field",
            "attrs": {"name": "display_name"},
            "xpath_info": [
                {"tag": "kanban", "indice": 1},
                {"tag": "card", "indice": 1},
                {"tag": "templates", "indice": 1},
                {"tag": "t", "indice": 1},
                {"tag": "field", "indice": 1},
            ],
        }
        operations = [
            {
                "type": "add",
                "target": target,
                "position": "after",
                "node": {"tag": "field", "attrs": {"name": "phone"}},
            },
            {
                "type": "remove",
                "target": target,
            },
        ]

        self.edit_view(inherited_kanban_view, operations=operations)

        self.assertViewArchEqual(
            inherited_kanban_view.get_combined_arch(),
            """
                <kanban default_group_by="country_id">
                    <card>
                        <templates>
                            <t t-name="card">
                                <field name="phone"/>
                                <field name="email"/>
                            </t>
                        </templates>
                    </card>
                </kanban>
            """,
        )

    def test_view_has_studio_key(self):
        view = self.env["ir.ui.view"].create({
            "name": "test",
            "type": "form",
            "model": "res.partner",
            "arch": """<form><field name="display_name" /></form>"""
        })

        self.assertFalse(view.key)
        self.assertFalse(view.xml_id)

        view.with_context(studio=1).write({"name": "test_written"})
        view.invalidate_recordset()
        self.assertTrue(view.key.startswith("studio_customization."))
        self.assertEqual(view.key, view.xml_id)

        view_2 = self.env["ir.ui.view"].with_context(studio=1).create({
            "name": "test",
            "type": "form",
            "model": "res.partner",
            "arch": """<form><field name="display_name" /></form>"""
        })
        self.assertTrue(view_2.key.startswith("studio_customization."))
        self.assertEqual(view_2.key, view_2.xml_id)
