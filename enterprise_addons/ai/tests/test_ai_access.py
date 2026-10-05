# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, HttpCase, JsonRpcException, tagged, users
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestAiFieldsAccess(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_user = new_test_user(cls.env, 'internal')
        cls.portal_user = new_test_user(cls.env, 'portal_user', 'base.group_portal')

    def test_ai_access_agent_system(self):
        # system: every right
        agent = self.env['ai.agent'].create({'name': 'test agent'})
        agent.write({'subtitle': 'bloups'})
        self.assertEqual(self.env['ai.agent'].search([('name', '=', 'test agent')]), agent)
        agent.unlink()
        self.assertFalse(agent.exists())

    @users('internal')
    def test_ai_access_agent_internal(self):
        # internal: readonly
        with self.assertRaises(AccessError):
            self.env['ai.agent'].create({'name': 'test agent'})
        agent_sudo = self.env['ai.agent'].sudo().create({'name': 'test agent'})
        agent = self.env['ai.agent'].search([('name', '=', 'test agent')])
        self.assertEqual(agent, agent_sudo)
        self.assertEqual('test agent', agent.name)
        with self.assertRaises(AccessError):
            agent.write({'subtitle': 'bloups'})
        with self.assertRaises(AccessError):
            agent.unlink()

    def test_ai_access_embedding_system(self):
        # system: every right
        attachment = self.env['ir.attachment'].create({
            'name': 'test attachment',
            'raw': b'test',
            'res_model': 'ai.embedding',
            'res_id': 0,
        })
        embedding = self.env['ai.embedding'].create({
            'res_id': attachment.id,
            'res_model': 'ir.attachment',
            'content': 'test content',
            'embedding_model': 'embedding_model',
        })
        embedding.write({'content': 'updated content'})
        self.assertEqual(
            self.env['ai.embedding'].search([('id', '=', embedding.id)]),
            embedding
        )
        embedding.unlink()
        self.assertFalse(embedding.exists())

    @users('internal')
    def test_ai_access_embedding_internal(self):
        # internal: readonly
        attachment = self.env['ir.attachment'].create({
            'name': 'test attachment',
            'raw': b'test',
            'res_model': 'ai.embedding',
            'res_id': 0,
        })
        with self.assertRaises(AccessError):
            self.env['ai.embedding'].create({
                'res_id': attachment.id,
                'res_model': 'ir.attachment',
                'content': 'test content',
                'embedding_model': 'embedding_model',
            })
        embedding_sudo = self.env['ai.embedding'].sudo().create({
            'res_id': attachment.id,
            'res_model': 'ir.attachment',
            'content': 'test content',
            'embedding_model': 'embedding_model',
        })
        with self.assertRaises(AccessError):
            embedding = self.env['ai.embedding'].search([('id', '=', embedding_sudo.id)])
            self.assertEqual(embedding, embedding_sudo)
            self.assertEqual('test content', embedding.content)
        with self.assertRaises(AccessError):
            embedding_sudo.sudo(False).write({'content': 'updated content'})
        with self.assertRaises(AccessError):
            embedding_sudo.sudo(False).unlink()

    def test_ai_access_skill_system(self):
        # system: every right
        skill = self.env['ai.skill'].create({
            'name': 'test skill',
            'description': 'skill description',
        })
        skill.write({'description': 'updated skill description'})
        self.assertEqual(
            self.env['ai.skill'].search([('id', '=', skill.id)]),
            skill
        )
        skill.unlink()
        self.assertFalse(skill.exists())

    @users('internal')
    def test_ai_access_skill_internal(self):
        # internal: readonly
        with self.assertRaises(AccessError):
            self.env['ai.skill'].create({
                'name': 'test skill',
                'description': 'skill description',
            })
        skill_sudo = self.env['ai.skill'].sudo().create({
            'name': 'test skill',
            'description': 'skill description',
        })
        skill = self.env['ai.skill'].search([('id', '=', skill_sudo.id)])
        self.assertEqual(skill, skill_sudo)
        self.assertEqual('test skill', skill.name)
        with self.assertRaises(AccessError):
            skill.write({'description': 'updated skill description'})
        with self.assertRaises(AccessError):
            skill.unlink()

    def test_create_ai_chat_with_restriced_record(self):
        """User should not be able to create a chat linked to a not accessible record
        """
        user = self.internal_user
        partner = self.env['res.partner'].create({'name': "Partner"})
        # remove res.partner read access from the user
        self.env['ir.access'].search([
            ('model_id.model', '=', 'res.partner'),
            ('group_id', 'in', user.all_group_ids.ids)
        ]).active = False
        self.env['ir.access'].create({
            'name': 'all except partner',
            'model_id': self.env['ir.model']._get('res.partner').id,
            'group_id': self.env.ref('base.group_user').id,
            'operation': 'r',
            'domain': str([('id', '!=', partner.id)]),
        })

        with self.assertRaises(AccessError):
            self.env['ai.agent'].with_user(user).action_launch_ai_chat('mail_composer', 'res.partner', partner.id)

    def test_chat_with_restriced_record(self):
        """Make sure that when access to a record is lost, new messages can't be sent anymore
        """
        user = self.internal_user
        partner = self.env['res.partner'].create({'name': "Partner"})
        session_data = self.env['ai.agent'].action_launch_ai_chat(
            'chatter_ai_button',
            'res.partner',
            partner.id,
            'test',
            None,
            None,
            None,
        )
        # remove res.partner read access from the user
        access_records = self.env['ir.access'].search([
            ('model_id.model', '=', 'res.partner'),
            ('group_id', 'in', user.all_group_ids.ids),
        ])
        access_records.active = False
        session = self.env['ai.session'].search([('channel_id', '=', session_data['ai_channel_id'])])
        with self.assertRaises(AccessError):
            session.with_user(user).sudo()._submit_agent_request([
                {'type': 'text', 'text': "Hello"},
            ])

    @mute_logger('odoo.http')
    def test_direct_response_portal(self):
        """Check that get_direct_response cannot be used by portal users
        """
        self.authenticate('portal_user', 'portal_user')
        with self.assertRaises(JsonRpcException, msg='odoo.exceptions.AccessError'):
            self.make_jsonrpc_request(
                "/ai/get_direct_response",
                {
                    "interface_key": "systray_ai_button",
                    "prompt": "<p>Test prompt</p>",
                }
            )

    def test_get_tool_params_requires_channel_access(self):
        """Internal users can read tool parameters only from channels they can access."""
        agent = self.env['ai.agent'].create({'name': 'Test Agent'})
        channel = agent._create_ai_chat_channel().with_user(self.internal_user)
        session = self.env['ai.session'].create({
            'agent_id': agent.id,
            'channel_id': channel.id,
        })
        event = self.env['ai.session.event'].create({
            'ai_session_id': session.id,
            'metadata': {'role': 'assistant', 'content': [{
                'type': 'tool_call',
                'name': 'test_tool',
                'call_id': 'call_1',
                'args': {"value": "test"},
            }]},
        }).with_user(self.internal_user)

        self.assertFalse(session.with_user(self.internal_user).has_access('read'))
        self.assertFalse(event.has_access('read'))
        self.assertFalse(channel.has_access('read'))
        with self.assertRaises(AccessError):
            event.get_tool_params('call_1')

        self.env['discuss.channel.member'].create({
            'channel_id': channel.id,
            'partner_id': self.internal_user.partner_id.id,
        })
        self.assertTrue(channel.has_access('read'))
        self.assertEqual(event.get_tool_params('call_1'), {'value': 'test'})
