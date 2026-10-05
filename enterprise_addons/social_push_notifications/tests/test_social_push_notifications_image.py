# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import tagged, HttpCase
from odoo.tools.image import binary_to_image


@tagged('at_install', '-post_install')  # LEGACY at_install
class SocialPushNotificationsImageCase(HttpCase):
    def test_push_image_is_accessible(self):
        pixel = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC'
        social_post = self.env['social.post'].create({
            'message': 'TestMessage',
            'push_notification_title': 'PushNotificationTitle',
            'push_notification_image': pixel
        })

        response = self.url_open('/social_push_notifications/social_post/%s/push_notification_image' % social_post.id)
        image = binary_to_image(response.content)
        width, _ = image.size
        # If Social Post isn't in posted or posting state, a placeholder should be rendered
        self.assertTrue(width > 1)

        social_post.write({'state': 'posted'})
        response = self.url_open('/social_push_notifications/social_post/%s/push_notification_image' % social_post.id)
        image = binary_to_image(response.content)
        width, _ = image.size
        # As Social Post is posted now, the pixel should be rendered
        self.assertTrue(width == 1)
