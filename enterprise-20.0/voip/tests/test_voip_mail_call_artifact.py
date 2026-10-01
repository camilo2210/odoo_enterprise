from psycopg2 import IntegrityError

from datetime import timedelta
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.addons.mail.tests.common import MailCommon
from odoo.tests.common import tagged
from odoo.tools import mute_logger


@tagged("call_artifacts")
class TestVoipMailCallArtifact(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call = cls.env["voip.call"].create({"phone_number": "8675309"})

        cls.demo_provider = cls.env["voip.provider"].create({
            "name": "Demo Provider",
            "mode": "demo",
        })
        cls.prod_provider = cls.env["voip.provider"].create({
            "name": "Prod Provider",
            "mode": "prod",
        })

        cls.user_demo = cls.user_employee
        cls.user_demo.res_users_settings_id.voip_provider_id = cls.demo_provider.id

        cls.user_prod = cls.user_employee_c2
        cls.user_prod.res_users_settings_id.voip_provider_id = cls.prod_provider.id

    def test_gc_demo_recordings(self):
        """Verify that the autovacuum correctly deletes only demo artifacts"""
        call_demo = self.env["voip.call"].create({
            "user_id": self.user_demo.id,
            "phone_number": "123",
            "is_production": False,
        })
        call_prod = self.env["voip.call"].create({
            "user_id": self.user_prod.id,
            "phone_number": "456",
            "is_production": True,
        })

        # Case: Old Demo (Should be deleted)
        art_old_demo = self.env["mail.call.artifact"].create({
            "voip_call_id": call_demo.id,
            "start_ms": 0, "end_ms": 1000,
        })
        self.env.cr.execute("UPDATE mail_call_artifact SET create_date = %s WHERE id = %s",
                           (fields.Datetime.now() - timedelta(days=2), art_old_demo.id))

        # Case: New Demo (Should NOT be deleted)
        art_new_demo = self.env["mail.call.artifact"].create({
            "voip_call_id": call_demo.id,
            "start_ms": 1000, "end_ms": 2000,
        })

        # Case: Old Prod (Should NOT be deleted)
        art_old_prod = self.env["mail.call.artifact"].create({
            "voip_call_id": call_prod.id,
            "start_ms": 0, "end_ms": 1000,
        })
        self.env.cr.execute("UPDATE mail_call_artifact SET create_date = %s WHERE id = %s",
                           (fields.Datetime.now() - timedelta(days=2), art_old_prod.id))

        # Run GC
        self.env["mail.call.artifact"]._gc_demo_recordings()

        self.assertFalse(art_old_demo.exists(), "Old demo artifact should have been vacuumed")
        self.assertTrue(art_new_demo.exists(), "Recent demo artifact should be preserved")
        self.assertTrue(art_old_prod.exists(), "Old production artifact should be preserved")

    def test_voip_artifact_overlap(self):
        self.env["mail.call.artifact"].create({"voip_call_id": self.call.id, "start_ms": 0, "end_ms": 1000})

        # No overlap -> OK
        self.env["mail.call.artifact"].create({"voip_call_id": self.call.id, "start_ms": 2000, "end_ms": 3000})

        # Overlap -> Error
        with self.assertRaises(ValidationError):
            self.env["mail.call.artifact"].create({"voip_call_id": self.call.id, "start_ms": 2500, "end_ms": 3500})

    @mute_logger("odoo.sql_db", "odoo.models")
    def test_artifact_must_be_related_to_single_call_model(self):
        """Ensure that an artifact is linked to exactly one call source"""
        # Both references set -> Error
        channel = self.env["discuss.channel"].create({"name": "Test Channel"})
        discuss_call = self.env["discuss.call.history"].create({
            "start_dt": fields.Datetime.now(),
            "channel_id": channel.id,
        })
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["mail.call.artifact"].create({
                    "voip_call_id": self.call.id,
                    "discuss_call_history_id": discuss_call.id,
                    "start_ms": 0,
                    "end_ms": 1000,
                })

        # None set -> Error
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["mail.call.artifact"].create({
                    "start_ms": 0,
                    "end_ms": 1000,
                })

    def test_voip_call_unlink_cascades_to_attachments(self):
        artifact = self.env["mail.call.artifact"].create({
            "voip_call_id": self.call.id,
            "start_ms": 0,
            "end_ms": 1000,
        })
        attachment = self.env["ir.attachment"].create({
            "name": "recording.wav",
            "res_model": "mail.call.artifact",
            "res_id": artifact.id,
            "raw": b"audio",
        })
        self.assertTrue(attachment.exists())
        self.call.unlink()
        self.assertFalse(self.call.exists())
        self.assertFalse(artifact.exists(), "The call's artifact should be deleted with the call.")
        self.assertFalse(attachment.exists(), "The artifact's attachment should be purged with the call.")
