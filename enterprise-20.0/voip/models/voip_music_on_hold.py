from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class VoipMusicOnHold(models.Model):
    _name = "voip.music.on.hold"
    _description = "VoIP Music on Hold"

    name = fields.Char(required=True)
    sort = fields.Selection(
        [
            ("alphabetical", "In Order"),
            ("random", "Random"),
            ("random_start", "Random Start"),
        ],
        required=True,
        default="alphabetical",
    )
    track_ids = fields.One2many(
        "voip.music.on.hold.track",
        "music_on_hold_id",
        string="Tracks",
    )
    pbx_moh_uuid = fields.Char(
        string="PBX MOH UUID",
        copy=False,
        groups="base.group_system",
    )
    pbx_moh_name = fields.Char(
        string="PBX MOH Name",
        copy=False,
        groups="base.group_system",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super(VoipMusicOnHold, self.with_context(voip_skip_pbx_sync=True)).create(vals_list)
        if not self.env.context.get("voip_skip_pbx_sync"):
            records.with_context(voip_skip_pbx_sync=False)._sync_pbx()
        # Return records bound to the caller's own context, not the
        # `voip_skip_pbx_sync=True` override used for the super() call above
        # — otherwise a later write()/unlink() on this same recordset would
        # silently skip PBX sync/cleanup.
        return records.with_env(self.env)

    def write(self, vals):
        result = super(VoipMusicOnHold, self.with_context(voip_skip_pbx_sync=True)).write(vals)
        if (
            {"name", "sort", "track_ids"} & vals.keys()
            and not self.env.context.get("voip_skip_pbx_sync")
        ):
            self._sync_pbx()
        return result

    @api.ondelete(at_uninstall=False)
    def _unlink_pbx_resources(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        moh_uuid_by_id = {
            moh.id: moh.pbx_moh_uuid
            for moh in self.sudo().filtered("pbx_moh_uuid")
        }
        if not moh_uuid_by_id:
            return

        def _delete(env, moh_id):
            env["voip.pbx.service"]._delete_moh(moh_uuid=moh_uuid_by_id[moh_id])

        self.env["voip.pbx.service"]._call_after_commit_for_deleted(
            "voip.music.on.hold", list(moh_uuid_by_id), _delete,
        )

    def _sync_pbx(self):
        if self.env.context.get("voip_skip_pbx_sync"):
            return
        service = self.env["voip.pbx.service"]
        for music_on_hold in self.sudo():
            files = [
                (
                    f"{index:03d}_odoo_audio_{track.audio_message_id.id}.wav",
                    track.audio_message_id._get_telephony_wav_content(),
                )
                for index, track in enumerate(
                    music_on_hold.track_ids.sorted("sequence"),
                    start=1,
                )
            ]
            result = service._sync_moh(
                moh_uuid=music_on_hold.pbx_moh_uuid or None,
                odoo_moh_id=music_on_hold.id,
                moh_name=music_on_hold.name,
                sort=music_on_hold.sort,
                files=files,
            )
            music_on_hold.with_context(voip_skip_pbx_sync=True).write({
                "pbx_moh_uuid": result["moh_uuid"],
                "pbx_moh_name": result["moh_name"],
            })


class VoipMusicOnHoldTrack(models.Model):
    _name = "voip.music.on.hold.track"
    _description = "VoIP Music on Hold Track"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    music_on_hold_id = fields.Many2one(
        "voip.music.on.hold",
        required=True,
        index=True,
        ondelete="cascade",
    )
    audio_message_id = fields.Many2one(
        "voip.sound",
        string="Sound",
        required=True,
        index=True,
        domain=[("data", "!=", False)],
        ondelete="restrict",
    )
    filename = fields.Char(related="audio_message_id.data_filename")

    @api.constrains("audio_message_id")
    def _check_wav_audio(self):
        for track in self:
            if (
                not track.audio_message_id.data
                or not (track.audio_message_id.data_filename or "").lower().endswith(".wav")
            ):
                raise ValidationError(_("Music on hold tracks must use WAV audio files."))
