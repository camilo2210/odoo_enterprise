import logging
import uuid
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.modules import module

from odoo.addons.voip.models.phone_service_api import (
    CLIENT_SECRET_PARAM,
    CLIENT_UUID_PARAM,
    ENDPOINT_PARAM,
    WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM,
    PhoneServiceAPI,
    validate_phone_service_endpoint,
)

_logger = logging.getLogger(__name__)


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("key") == ENDPOINT_PARAM and vals.get("value"):
                validate_phone_service_endpoint(self.env, vals["value"])
        configs = super().create(vals_list)
        if any(vals.get("key") == "web.base.url" for vals in vals_list):
            self._voip_try_sync_webhook_event_url(notify_user=True)
        return configs

    def write(self, vals):
        if vals.get("value") and any(config.key == ENDPOINT_PARAM for config in self):
            validate_phone_service_endpoint(self.env, vals["value"])
        res = super().write(vals)
        if any(config.key == "web.base.url" for config in self):
            self._voip_try_sync_webhook_event_url(notify_user=True)
        return res

    def _voip_try_sync_webhook_event_url(self, notify_user=False):
        if module.current_test:
            # Do not call phone_service during tests.
            return
        try:
            PhoneServiceAPI(self.env).sync_webhook_event_url()
        except UserError:
            _logger.warning(
                "Could not sync VoIP webhook URL with phone_service; it will be retried by cron.",
                exc_info=True,
            )
            self.sudo().set_bool(WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM, True)
            self.env.ref("voip.ir_cron_voip_sync_webhook_event_url")._trigger(
                at=fields.Datetime.now() + timedelta(hours=1)
            )
            if notify_user:
                self.env.user._bus_send(
                    "simple_notification",
                    {
                        "type": "warning",
                        "title": self.env._("VoIP webhook sync failed"),
                        "message": self.env._(
                            "The VoIP webhook URL could not be synchronized with "
                            "the Phone Service. It will be retried automatically."
                        ),
                        "sticky": False,
                    },
                )

    def _voip_get_client_credentials(self):
        icp = self.sudo()
        client_uuid = icp.get_str(CLIENT_UUID_PARAM)
        if not client_uuid:
            client_uuid = str(uuid.uuid4())
            icp.set_str(CLIENT_UUID_PARAM, client_uuid)
        client_secret = icp.get_str(CLIENT_SECRET_PARAM)
        if not client_secret:
            client_secret = str(uuid.uuid4())
            icp.set_str(CLIENT_SECRET_PARAM, client_secret)
        return client_uuid, client_secret

    @api.model
    def _cron_sync_webhook_event_url(self):
        if self.sudo().get_bool(WEBHOOK_EVENT_URL_SYNC_PENDING_PARAM):
            self._voip_try_sync_webhook_event_url()
