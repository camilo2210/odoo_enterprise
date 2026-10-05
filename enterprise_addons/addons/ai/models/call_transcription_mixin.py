from odoo import models


class CallTranscriptionMixin(models.AbstractModel):
    """Define the interface for post-transcription hooks.

    Models representing calls (e.g., discuss.call.history, voip.call) should
    inherit from this mixin to implement specific behavior after an artifact
    is transcribed or when all artifacts of a call are processed."""
    _name = "call.transcription.mixin"
    _description = "Call Transcription Mixin"

    def _after_artifact_transcription_done(self, artifact):
        """Execute hook after a single artifact has been successfully transcribed
        :param artifact: the call.artifact record that was transcribed.
        """
        pass

    def _after_artifact_transcription_error(self, artifact):
        """Execute hook after a single artifact transcription failed
        :param artifact: the call.artifact record that failed to transcribe.
        """
        pass

    def _after_all_artifacts_transcribed(self):
        """Execute hook after all STT artifacts of a call have been processed
        (either successfully or with a terminal error).
        """
        pass
