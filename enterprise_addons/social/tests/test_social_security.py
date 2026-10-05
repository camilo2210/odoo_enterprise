# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.addons.social.tests import common
from odoo.addons.social.tests.tools import mock_void_external_calls
from odoo.fields import Domain
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import users
from odoo.tools import mute_logger


@tagged('security')
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestAccess(common.SocialCase):
    @classmethod
    def setUpClass(cls):
        """ Create some more dummy data for security tests. """
        super(TestAccess, cls).setUpClass()

        with mock_void_external_calls():
            cls.social_live_post = cls.env['social.live.post'].create({
                'post_id': cls.social_post.id,
                'account_id': cls.social_account.id
            })

            cls.social_stream_type = cls.env['social.stream.type'].create({
                'name': 'My Stream Type',
                'stream_type': 'my_stream_type',
                'media_id': cls.social_media.id
            })

            cls.social_stream = cls.env['social.stream'].create({
                'account_id': cls.social_account.id,
                'stream_type_id': cls.social_stream_type.id,
                'media_id': cls.social_media.id
            })

            cls.social_stream_post = cls.env['social.stream.post'].create({
                'message': 'A stream post',
                'stream_id': cls.social_stream.id,
            })

            cls.social_stream_post_image = cls.env['social.stream.post.attachment'].create({
                'attachment_content_type': 'image',
                'content_url': 'dummy.png',
                'stream_post_id': cls.social_stream_post.id,
            })

    @mute_logger('odoo.addons.base.models.ir_access')
    @users('user_emp')
    @mock_void_external_calls()
    def test_access_social_employee(self):
        # Create: not allowed
        with self.assertRaises(AccessError):
            self.env['social.post'].create({'message': 'A Post'})
        with self.assertRaises(AccessError):
            self.env['social.live.post'].create({'post_id': self.social_post.id, 'account_id': self.social_account.id})
        with self.assertRaises(AccessError):
            self.env['social.account'].create({'name': 'An account', 'media_id': self.social_media.id})
        with self.assertRaises(AccessError):
            self.env['social.media'].create({'name': 'A media'})
        with self.assertRaises(AccessError):
            self.env['social.stream'].create({'name': 'A stream', 'account_id': self.social_account.id})
        with self.assertRaises(AccessError):
            self.env['social.stream.type'].create({'name': 'A stream type'})
        with self.assertRaises(AccessError):
            self.env['social.stream.post'].create({'message': 'A stream post'})
        with self.assertRaises(AccessError):
            self.env['social.stream.post.attachment'].create({
                'content_url': 'dummy.png',
                'attachment_content_type': 'image',
                'stream_post_id': self.social_stream_post.id,
            })

        # Read: not allowed
        with self.assertRaises(AccessError):
            self.social_post.with_user(self.env.user).read(['message'])
        with self.assertRaises(AccessError):
            self.social_live_post.with_user(self.env.user).read(['post_id'])
        with self.assertRaises(AccessError):
            self.social_account.with_user(self.env.user).read(['name'])
        with self.assertRaises(AccessError):
            self.social_media.with_user(self.env.user).read(['name'])
        with self.assertRaises(AccessError):
            self.social_stream.with_user(self.env.user).read(['media_id'])
        with self.assertRaises(AccessError):
            self.social_stream_type.with_user(self.env.user).read(['media_id'])
        with self.assertRaises(AccessError):
            self.social_stream_post.with_user(self.env.user).read(['message'])
        with self.assertRaises(AccessError):
            self.social_stream_post_image.with_user(self.env.user).read(['stream_post_id'])

        # Write: not allowed
        with self.assertRaises(AccessError):
            self.social_post.with_user(self.env.user).write({'message': 'New Message'})
        with self.assertRaises(AccessError):
            self.social_live_post.with_user(self.env.user).write({'post_id': self.social_post.id})
        with self.assertRaises(AccessError):
            self.social_account.with_user(self.env.user).write({'name': 'New Name'})
        with self.assertRaises(AccessError):
            self.social_media.with_user(self.env.user).write({'name': 'New Name'})
        with self.assertRaises(AccessError):
            self.social_stream.with_user(self.env.user).write({'media_id': self.social_media.id})
        with self.assertRaises(AccessError):
            self.social_stream_type.with_user(self.env.user).write({'media_id': self.social_media.id})
        with self.assertRaises(AccessError):
            self.social_stream_post.with_user(self.env.user).write({'message': 'New Message'})
        with self.assertRaises(AccessError):
            self.social_stream_post_image.with_user(self.env.user).write({'stream_post_id': self.social_stream_post.id})

        # Unlink: not allowed
        with self.assertRaises(AccessError):
            self.social_post.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_live_post.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_account.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_media.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_stream.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_stream_type.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_stream_post.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_stream_post_image.with_user(self.env.user).unlink()

    @mute_logger('odoo.addons.base.models.ir_access')
    @users('social_user')
    @mock_void_external_calls()
    def test_access_social_social_user(self):
        # Create: not allowed except for posts, live posts (as able to post a post) and streams
        new_post = self.env['social.post'].create({'message': 'A Post'})
        new_stream = self.env['social.stream'].create({
            'media_id': self.social_media.id,
            'stream_type_id': self.social_stream_type.id,
            'account_id': self.social_account.id
        })
        # can access all the posts. -> can post all posts
        self.env['social.live.post'].create({
            'post_id': self.social_post.id,
            'account_id': self.social_account.id
        })
        new_live_post = self.env['social.live.post'].create({
            'post_id': new_post.id,
            'account_id': self.social_account.id
        })

        with self.assertRaises(AccessError):
            self.env['social.account'].create({'name': 'An account', 'media_id': self.social_media.id})
        with self.assertRaises(AccessError):
            self.env['social.media'].create({'name': 'A media'})
        with self.assertRaises(AccessError):
            self.env['social.stream.type'].create({'name': 'A stream type'})
        with self.assertRaises(AccessError):
            self.env['social.stream.post'].create({'message': 'A stream post'})
        with self.assertRaises(AccessError):
            self.env['social.stream.post.attachment'].create({
                'attachment_content_type': 'image',
                'content_url': 'dummy.png',
                'stream_post_id': self.social_stream_post.id,
            })

        # Can post
        new_post.action_post_now()

        # Read: allowed. They can read all posts
        new_post.with_user(self.env.user).read(['message'])
        self.social_post.with_user(self.env.user).read(['message'])

        new_live_post.with_user(self.env.user).read(['post_id'])
        self.social_live_post.with_user(self.env.user).read(['post_id'])

        self.social_account.with_user(self.env.user).read(['name'])
        self.social_media.with_user(self.env.user).read(['name'])
        self.social_stream.with_user(self.env.user).read(['media_id'])
        self.social_stream_type.with_user(self.env.user).read(['media_id'])
        self.social_stream_post.with_user(self.env.user).read(['message'])
        self.social_stream_post_image.with_user(self.env.user).read(['stream_post_id'])

        # Write: allowed
        new_post.with_user(self.env.user).write({'message': 'New Message'})
        new_stream.with_user(self.env.user).write({'name': 'New Name'})
        self.social_post.with_user(self.env.user).write({'message': 'New Message'})
        # can now write on the 'state' field
        new_post.with_user(self.env.user).write({'state': 'scheduled'})
        new_live_post.with_user(self.env.user).write({'post_id': self.social_post.id})
        self.social_live_post.with_user(self.env.user).write({'post_id': self.social_post.id})

        with self.assertRaises(AccessError):
            self.social_account.with_user(self.env.user).write({'name': 'New Name'})
        with self.assertRaises(AccessError):
            self.social_media.with_user(self.env.user).write({'name': 'New Name'})
        with self.assertRaises(AccessError):
            self.social_stream.with_user(self.env.user).write({'media_id': self.social_media.id})
        with self.assertRaises(AccessError):
            self.social_stream_type.with_user(self.env.user).write({'media_id': self.social_media.id})
        with self.assertRaises(AccessError):
            self.social_stream_post.with_user(self.env.user).write({'message': 'New Message'})
        with self.assertRaises(AccessError):
            self.social_stream_post_image.with_user(self.env.user).write({'stream_post_id': self.social_stream_post.id})

        # Unlink: not allowed except for their own posts/streams/live posts
        new_post.with_user(self.env.user).unlink()
        new_stream.with_user(self.env.user).unlink()
        new_live_post.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_post.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_live_post.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_account.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_media.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_stream.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_stream_type.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_stream_post.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_stream_post_image.with_user(self.env.user).unlink()

        # Test that we cannot read any attachment by abusing `social.post.image`
        restricted_record = self.env["ir.config_parameter"].sudo().create({
            "key": "social.test_restricted_attachment",
            "value": "test",
        })
        attachment = self.env["ir.attachment"].sudo().create(
            {"res_model": restricted_record._name, "res_id": restricted_record.id, "name": "test", "raw": b"original"}
        ).with_user(self.env.user)
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            attachment.name
        with self.assertRaises(AccessError):
            self.env["social.post.image"].create({"attachment_id": attachment.id})
        with self.assertRaises(AccessError):
            self.env["social.post.image"].onchange(
                {"attachment_id": attachment.id},
                ["attachment_id"],
                {"raw": {}},
            )
        with self.assertRaises(AccessError):
            self.env["social.post.image"].with_context(
                default_attachment_id=attachment.id,
            ).onchange(
                {},
                [],
                {"attachment_id": {}, "raw": {}},
            )

        self.env["ir.default"].set(
            "social.post.image",
            "attachment_id",
            attachment.id,
            user_id=True,
        )
        with self.assertRaises(AccessError):
            self.env["social.post.image"].onchange(
                {},
                [],
                {"attachment_id": {}, "raw": {}},
            )
        image = self.env["social.post.image"].sudo().create({"attachment_id": attachment.id}).sudo(False)
        self.env.invalidate_all()
        self.assertEqual(image.raw.content, b"original", "Should be able to read image created by other users")
        with self.assertRaises(AccessError):
            image.raw = b'updated'
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(attachment.sudo().raw.content, b"original", "Cannot update the attachment using the social image")

        def attachment_access_domain(rec, operation):
            # can read but not write the attachment
            return Domain.TRUE if operation == "read" else Domain.FALSE

        with patch.object(self.env.registry['ir.attachment'], '_access_domain', attachment_access_domain):
            self.env["social.post.image"].create({"attachment_id": attachment.id})

            with self.assertRaises(AccessError):
                self.env["social.post.image"].create({"attachment_id": attachment.id, 'name': 'test name'})

    @mute_logger('odoo.addons.base.models.ir_access')
    @users('social_manager')
    @mock_void_external_calls()
    def test_access_social_social_manager(self):
        # Create: allowed except for media and stream types
        new_post = self.env['social.post'].create({'message': 'A Post', 'account_ids': [(4, self.social_account.id)]})
        self.env['social.live.post'].create({'post_id': self.social_post.id, 'account_id': self.social_account.id})
        self.env['social.account'].create({'name': 'An account', 'media_id': self.social_media.id})
        self.env['social.stream'].create({
            'media_id': self.social_media.id,
            'stream_type_id': self.social_stream_type.id,
            'account_id': self.social_account.id
        })
        self.env['social.stream.post'].create({'message': 'A stream post', 'stream_id': self.social_stream.id})
        self.env['social.stream.post.attachment'].create({
            'attachment_content_type': 'image',
            'content_url': 'dummy.png',
            'stream_post_id': self.social_stream_post.id,
        })

        with self.assertRaises(AccessError):
            self.env['social.media'].create({'name': 'A media'})
        with self.assertRaises(AccessError):
            self.env['social.stream.type'].create({'name': 'A stream type'})

        # Can post
        new_post.action_post_now()

        # Read: allowed
        self.social_post.with_user(self.env.user).read(['message'])
        self.social_live_post.with_user(self.env.user).read(['post_id'])
        self.social_account.with_user(self.env.user).read(['name'])
        self.social_media.with_user(self.env.user).read(['name'])
        self.social_stream.with_user(self.env.user).read(['media_id'])
        self.social_stream_type.with_user(self.env.user).read(['media_id'])
        self.social_stream_post.with_user(self.env.user).read(['message'])
        self.social_stream_post_image.with_user(self.env.user).read(['stream_post_id'])

        # Write: allowed except for stream types
        self.social_media.with_user(self.env.user).write({'name': 'New Name'})
        self.social_post.with_user(self.env.user).write({'message': 'New Message', 'state': 'scheduled'})
        self.social_live_post.with_user(self.env.user).write({'post_id': self.social_post.id})
        self.social_account.with_user(self.env.user).write({'name': 'New Name'})
        self.social_stream.with_user(self.env.user).write({'media_id': self.social_media.id})
        self.social_stream_post.with_user(self.env.user).write({'message': 'New Message'})
        self.social_stream_post_image.with_user(self.env.user).write({'stream_post_id': self.social_stream_post.id})

        with self.assertRaises(AccessError):
            self.social_stream_type.with_user(self.env.user).write({'media_id': self.social_media.id})

        # Unlink: allowed except for media and stream types
        self.social_live_post.with_user(self.env.user).unlink()
        self.social_post.with_user(self.env.user).unlink()
        self.social_stream_post_image.with_user(self.env.user).unlink()
        self.social_stream_post.with_user(self.env.user).unlink()
        self.social_stream.with_user(self.env.user).unlink()
        self.social_account.with_user(self.env.user).unlink()

        with self.assertRaises(AccessError):
            self.social_media.with_user(self.env.user).unlink()
        with self.assertRaises(AccessError):
            self.social_stream_type.with_user(self.env.user).unlink()

    @classmethod
    def _get_social_media(cls):
        return cls.env['social.media'].create({
            'name': 'Social Media',
        })
