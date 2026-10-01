import logging
import operator
from os.path import splitext

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import BinaryBytes, config

from odoo.addons.voip.models.phone_service_api import PhoneServiceAPI
from odoo.addons.voip.tools import wav


PBX_AUDIO_SYNC_FIELDS = {"data", "data_filename"}
VOICEMAIL_GREETING_CHANNELS = 1
VOICEMAIL_GREETING_FRAME_RATE = 8000
VOICEMAIL_GREETING_SAMPLE_WIDTH = 2
# Mirrors the Odoo Phone Service's default phone_service.tts_max_text_length;
# kept here for immediate UI feedback, but the service call is the authority.
TTS_MAX_TEXT_LENGTH = 2000
FALLBACK_TTS_VOICE = {
    "voice_id": "Telnyx.NaturalHD.astra",
    "label": "Astra (English)",
    "language_code": "en",
    "language_name": "English (US)",
}

_logger = logging.getLogger(__name__)


class VoipSound(models.Model):
    _name = "voip.sound"
    _inherit = "voip.pbx.destination.mixin"
    _description = "PBX Sound"
    _order = "name"

    name = fields.Char(required=True)
    source_type = fields.Selection(
        [
            ("tts", "Text-to-speech"),
            ("upload", "Upload (.wav) or record"),
        ],
        required=True,
        default="tts",
    )
    tts_text = fields.Text(
        string="Text",
        help="Text that will be synthesized into an audio file.",
    )
    tts_voice = fields.Selection(
        selection="_get_tts_voice_selection",
        string="Voice",
        default="Telnyx.NaturalHD.astra",
        help="Telnyx voice identifier used to generate the audio.",
    )
    data = fields.Binary(
        string="File",
        attachment=True,
        help="Audio file to play. Upload an uncompressed PCM WAV file.",
    )
    data_filename = fields.Char(string="Filename")
    data_version = fields.Integer(default=0)
    generated_tts_text = fields.Text()
    generated_tts_voice = fields.Char()

    @api.model
    def _get_tts_voice_selection(self):
        return [(voice["voice_id"], voice["label"]) for voice in self._get_tts_voices_normalized()]

    @api.model
    def get_tts_voices_by_language(self):
        """RPC for the Voice widget: same voices as `_get_tts_voice_selection`,
        each tagged with its resolved language, the distinct list of languages
        actually available (to populate the Language filter), and which of
        those to preselect (the user's language, falling back to English)."""
        voices = self._get_tts_voices_normalized()
        languages = {
            voice["language_code"]: voice["language_name"]
            for voice in voices
            if voice["language_code"] and voice["language_name"]
        }
        languages_data = sorted(
            ({"code": code, "name": name} for code, name in languages.items()),
            key=operator.itemgetter("name"),
        )
        user_language_code = (self.env.user.lang or "").split("_")[0].lower()
        default_language_code = next(
            (
                code for code in (user_language_code, "en")
                if code in languages
            ),
            languages_data[0]["code"] if languages_data else None,
        )
        return {
            "voices": voices,
            "languages": languages_data,
            "default_language_code": default_language_code,
        }

    def _get_tts_voices_normalized(self):
        """Telnyx voices as ``{voice_id, label, language_code, language_name}``,
        sorted by label. Falls back to a single default voice in demo/test
        mode or when Telnyx is unreachable, so callers never end up with an
        empty voice list."""
        if config["test_enable"]:
            return [FALLBACK_TTS_VOICE]
        try:
            voices = self._get_tts_voices()
        except UserError:
            _logger.warning("Could not retrieve Telnyx TTS voices", exc_info=True)
            return [FALLBACK_TTS_VOICE]
        lang_names = self._get_lang_names_by_iso_code()
        normalized = []
        for voice in voices:
            voice_id = voice.get("voice_id")
            name = (voice.get("name") or "").strip()
            if not voice_id or not name or name.isdigit():
                # Skip catalog entries with no usable display name - some
                # come back from Telnyx with a bare numeric index (e.g.
                # "0"/"1") as their "name", which is meaningless to users.
                continue
            raw_language = voice.get("language") or ""
            language_code = raw_language.split("-")[0].split("_")[0].lower() or None
            normalized.append({
                "voice_id": voice_id,
                # No language in the label: the Language filter dropdown
                # already narrows the list to a single language.
                "label": " / ".join(filter(None, (
                    name,
                    voice.get("gender"),
                ))),
                "language_code": language_code,
                "language_name": language_code and lang_names.get(language_code),
            })
        normalized.sort(key=operator.itemgetter("label"))
        return normalized or [FALLBACK_TTS_VOICE]

    def _get_tts_voices(self):
        return self._get_tts_voices_cached(fields.Date.today())

    @api.ormcache("day")
    def _get_tts_voices_cached(self, day):
        # Telnyx's voice catalog is static and global, so fetch it once a day
        # and serve every lookup (Selection metadata, the Voice widget's RPC)
        # from memory. `day` only exists to key the cache with a daily TTL,
        # since there's no invalidation code — mirrors _get_coverage_map in
        # voip_did_number_search_wizard.py.
        return PhoneServiceAPI(self.env).get_tts_voices()

    @api.ormcache()
    def _get_lang_names_by_iso_code(self):
        # res.lang ships every world language regardless of install state
        # (only `active` differs), so this covers Telnyx's catalog without
        # requiring the matching Odoo language to be installed.
        langs = self.env["res.lang"].with_context(active_test=False).search_read(
            [("iso_code", "!=", False)], ["iso_code", "name"],
        )
        result = {}
        for lang in langs:
            result.setdefault(lang["iso_code"], lang["name"])
        return result

    @api.onchange("tts_text")
    def _onchange_tts_text(self):
        if (self.tts_text or "").strip():
            self.source_type = "tts"
        elif self.data:
            self.source_type = "upload"

    @api.constrains(
        "source_type",
        "tts_text",
        "tts_voice",
        "data",
        "generated_tts_text",
        "generated_tts_voice",
    )
    def _check_required_fields_per_source_type(self):
        for message in self:
            if message.source_type == "tts" and (
                not (message.tts_text or "").strip() or not message.tts_voice
            ):
                raise ValidationError(
                    _(
                        "For text-to-speech sounds, both Text and Voice must be set."
                    )
                )
            if message.source_type == "tts" and (
                not message.data
                or message.generated_tts_text != (message.tts_text or "").strip()
                or message.generated_tts_voice != message.tts_voice
            ):
                raise ValidationError(
                    _("Generate the audio before saving the text-to-speech sound.")
                )
            if message.source_type == "upload" and not message.data:
                raise ValidationError(
                    _("For uploaded sounds, an audio file must be provided.")
                )

    @api.constrains("tts_text")
    def _check_tts_text_length(self):
        for message in self:
            if len(message.tts_text or "") > TTS_MAX_TEXT_LENGTH:
                raise ValidationError(
                    _(
                        "The text is too long to be converted to speech (maximum"
                        " %(max_length)s characters).",
                        max_length=TTS_MAX_TEXT_LENGTH,
                    )
                )

    @api.constrains("source_type", "data", "data_filename")
    def _check_uploaded_wav(self):
        for message in self.filtered(lambda record: record.source_type == "upload" and record.data):
            if splitext(message.data_filename or "")[1].lower() != ".wav":
                raise ValidationError(_("Upload a WAV file."))
            try:
                frames, channels, sample_width, _frame_rate = wav.decode_wav(
                    message._get_audio_content(),
                )
                wav.decode_wav_samples(frames, sample_width, channels)
            except UserError as error:
                raise ValidationError(error.args[0]) from error

    @api.model
    def generate_tts_audio_preview(self, text, voice, name=None):
        self.check_access("create")
        tts_text = (text or "").strip()
        if not tts_text or not voice:
            raise UserError(_("Text and Voice are required to generate audio."))
        if len(tts_text) > TTS_MAX_TEXT_LENGTH:
            raise UserError(
                _(
                    "The text is too long to be converted to speech (maximum"
                    " %(max_length)s characters).",
                    max_length=TTS_MAX_TEXT_LENGTH,
                )
            )
        audio_bytes = PhoneServiceAPI(self.env).generate_speech(text=tts_text, voice=voice)
        if not audio_bytes:
            raise UserError(_("The Odoo Phone Service returned an empty audio file."))
        return {
            "content": BinaryBytes(audio_bytes).to_base64(),
            "filename": self._get_default_filename(name),
            "text": tts_text,
            "voice": voice,
        }

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if vals.get("source_type", "tts") == "tts" and not vals.get("data_filename"):
                vals["data_filename"] = self._get_default_filename(vals.get("name"))
        messages = super().create(vals_list)
        messages._sync_pbx()
        return messages

    def write(self, vals):
        vals = dict(vals)
        should_bump_data_version = "data" in vals and "data_version" not in vals
        should_sync_pbx = bool(PBX_AUDIO_SYNC_FIELDS & vals.keys())

        if should_bump_data_version:
            for message in self:
                super(VoipSound, message).write({
                    **vals,
                    "data_version": message.data_version + 1,
                })
            result = True
        else:
            result = super().write(vals)

        if should_sync_pbx:
            self._sync_pbx()
            if "data" in vals:
                self._sync_pbx_voicemail_greetings()
            self._sync_pbx_music_on_hold()
        return result

    def _get_default_filename(self, name=None):
        name = name or self.name or "audio_message"
        slug = self.env["ir.http"]._slugify(name) or "audio_message"
        return f"{slug}.wav"

    def _sync_pbx(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        messages = self.filtered("data")
        if not messages:
            return
        for message in messages:
            try:
                with self.env.cr.savepoint():
                    self.env["voip.pbx.service"]._upload_sound(
                        filename=message._get_pbx_sound_filename(),
                        content=message._get_pbx_sound_content(),
                        sound_format=message._get_pbx_sound_format(),
                    )
            except UserError as error:
                if self.env.context.get("voip_raise_pbx_sync_error"):
                    raise
                _logger.warning(
                    "Could not synchronize audio message %s with PBX: %s",
                    message.id,
                    error,
                )

    def _sync_pbx_voicemail_greetings(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        self.env["voip.voicemail"].sudo().search([
            ("audio_message_id", "in", self.ids),
        ])._sync_pbx()

    def _sync_pbx_music_on_hold(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        self.env["voip.music.on.hold.track"].search([
            ("audio_message_id", "in", self.ids),
        ]).music_on_hold_id._sync_pbx()

    def _get_audio_content(self):
        self.ensure_one()
        content = self.data.content
        if not isinstance(content, bytes):
            raise UserError(_("Audio message file must be stored as bytes."))
        return content

    def _get_duration_seconds(self):
        """Length of the underlying audio, in seconds; 0 without data yet."""
        self.ensure_one()
        if not self.data:
            return 0.0
        frames, channels, sample_width, frame_rate = wav.decode_wav(self._get_audio_content())
        if not frame_rate or not channels or not sample_width:
            return 0.0
        return len(frames) / (channels * sample_width) / frame_rate

    def _get_telephony_wav_content(self):
        self.ensure_one()
        frames, channels, sample_width, frame_rate = wav.decode_wav(
            self._get_audio_content()
        )

        samples = wav.decode_wav_samples(frames, sample_width, channels)
        if frame_rate != VOICEMAIL_GREETING_FRAME_RATE:
            samples = wav.resample_wav_samples(
                samples,
                frame_rate,
                VOICEMAIL_GREETING_FRAME_RATE,
            )

        return wav.encode_wav(
            wav.pack_int16_samples(samples),
            channels=VOICEMAIL_GREETING_CHANNELS,
            sample_width=VOICEMAIL_GREETING_SAMPLE_WIDTH,
            frame_rate=VOICEMAIL_GREETING_FRAME_RATE,
        )

    def _get_pbx_sound_content(self):
        self.ensure_one()
        if self._get_pbx_sound_format() == "wav":
            return self._get_telephony_wav_content()
        return self._get_audio_content()

    def _get_pbx_sound_filename(self):
        self.ensure_one()
        return f"odoo_audio_message_{self.id}"

    def _get_pbx_sound_format(self):
        self.ensure_one()
        extension = splitext(self.data_filename or "")[1].removeprefix(".").lower()
        return extension or "wav"
