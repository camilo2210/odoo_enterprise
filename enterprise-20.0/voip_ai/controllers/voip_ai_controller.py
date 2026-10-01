from werkzeug.exceptions import Forbidden

from odoo.http import request

from odoo.addons.ai.models.mail_call_artifact import TRANSCRIPTION_MAX_FILE_SIZE
from odoo.addons.voip.controllers.voip_controller import VoipController


class VoipAiController(VoipController):

    def _get_allowed_artifact_fields(self):
        return super()._get_allowed_artifact_fields() | {"is_stt", "transcription_state"}

    def _is_cloud_storage_required(self, call_sudo, **kwargs):
        """Prevent cloud storage requirement for STT uploads."""
        if kwargs.get('is_stt') == 'true':
            return False
        return super()._is_cloud_storage_required(call_sudo, **kwargs)

    def _create_artifact(self, vals, **kwargs):
        # Add an option to create artifacts that should be transcribed
        if kwargs.get('is_stt') == 'true':
            ufile = request.httprequest.files.get('ufile')
            if ufile:
                ufile.seek(0, 2)
                file_size = ufile.tell()
                ufile.seek(0)
                if file_size > TRANSCRIPTION_MAX_FILE_SIZE:
                    raise Forbidden()
            vals.update({
                'is_stt': True,
                'transcription_state': 'pending',
            })
        return super()._create_artifact(vals, **kwargs)
