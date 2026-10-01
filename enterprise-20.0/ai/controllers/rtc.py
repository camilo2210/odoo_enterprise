# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug.exceptions import BadRequest

from odoo.http import Response, request, route
from odoo.tools import str2bool

from odoo.addons.mail.controllers.discuss.rtc import RtcController, _check_jwt


class AIRtcController(RtcController):
    @route(
        "/mail/rtc/recording/<int:call_history_id>/transcribe",
        type="http",
        auth="public",
        methods=["POST"],
        cors="*",
        csrf=False,
        max_content_length=30 * 1024 * 1024,  # 30MB decent margin, expecting 1h of 32k audio (~15MB)
    )
    def transcribe_audio(self, call_history_id, start_ms, end_ms, has_media_output="true"):
        call_history_sudo = request.env["discuss.call.history"].sudo().browse(call_history_id).exists()
        claims = _check_jwt(request, call_history_sudo.channel_id)
        recording_started_by = request.env["res.users"].sudo().browse(
            claims.get("user_id"),
        ).exists()
        file_data = request.httprequest.get_data()
        if not file_data:
            raise BadRequest()
        start_ms, end_ms = self._get_recording_offsets(call_history_sudo, start_ms, end_ms)
        artifact_sudo = (
            request.env["mail.call.artifact"]
            .sudo()
            .create(
                {
                    "discuss_call_history_id": call_history_sudo.id,
                    "end_ms": end_ms,
                    "has_media_output": str2bool(has_media_output, default=False),
                    "is_stt": True,
                    "recording_started_by_id": recording_started_by.id,
                    "start_ms": start_ms,
                    "transcription_state": "pending",
                },
            )
        )
        request.env["ir.attachment"].sudo().create(
            {
                "mimetype": request.httprequest.content_type or "audio/ogg",
                "name": f"audio_{call_history_sudo.id}",
                "raw": file_data,
                "res_id": artifact_sudo.id,
                "res_model": "mail.call.artifact",
                "type": "binary",
            },
        )
        call_history_sudo._broadcast_recording_availability()
        artifact_sudo.action_transcribe_gevent()
        return Response(status=204)
