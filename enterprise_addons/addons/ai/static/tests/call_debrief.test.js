import { expect, describe, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryOne } from "@odoo/hoot-dom";
import { contains, startServer, start, openFormView, mailModels } from "@mail/../tests/mail_test_helpers";
import { fields, models, defineModels, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { CallDebrief } from "@mail/views/fields/call_debrief/call_debrief";

describe.current.tags("desktop", "call_debrief");

class MailCallArtifact extends models.Model {
    _name = "mail.call.artifact";

    transcript = fields.Text();
    is_stt = fields.Boolean();
    media_id = fields.Many2one({ relation: "ir.attachment" });
    recording_upload_pending = fields.Boolean();
    start_ms = fields.Integer();
    end_ms = fields.Integer();
    test_record_id = fields.Many2one({ relation: "test.call.record" });
}

class TestCallRecord extends models.Model {
    _name = "test.call.record";

    start_date = fields.Datetime();
    end_date = fields.Datetime();
    artifact_ids = fields.One2many({
        relation: "mail.call.artifact",
        relation_field: "test_record_id",
    });
}

defineModels({ ...mailModels, MailCallArtifact, TestCallRecord });

const AUDIO_FIXTURE_URL = "/mail/static/tests/fixtures/audio_60s.webm";
const VIDEO_FIXTURE_URL = "/mail/static/tests/fixtures/video_60s.webm";

/**
 * Creates a media artifact (audio or video) that maps to the 60-second fixture.
 * @param {Object} pyEnv The python environment
 * @param {Object} options
 * @param {number} options.start Start time in seconds relative to the call
 * @param {string} [options.type="audio"] "audio" or "video"
 * @returns {number} The created artifact ID
 */
function _createRecording(pyEnv, { start = 0, type = "audio" } = {}) {
    const duration = 60; // Always 60s to match the fixture length
    const attachmentId = pyEnv["ir.attachment"].create({
        name: `fixture_${start}_${type}.webm`,
        mimetype: type === "video" ? "video/webm" : "audio/webm",
    });
    return pyEnv["mail.call.artifact"].create({
        media_id: attachmentId,
        is_stt: false,
        start_ms: start * 1000,
        end_ms: (start + duration) * 1000,
    });
}

function _setupCallDebriefPatch() {
    patchWithCleanup(CallDebrief.prototype, {
        async _loadData(props) {
            await super._loadData(props);
            if (!this.state.mediaSegments) {
                return;
            }
            // Automatically inject the correct static fixture URL based on type
            for (const segment of this.state.mediaSegments) {
                segment.mediaUrl = segment.type === "video" ? VIDEO_FIXTURE_URL : AUDIO_FIXTURE_URL;
            }
        },
    });
}

async function _openDebriefView(pyEnv, testRecordId) {
    await openFormView("test.call.record", testRecordId, {
        arch: `
            <form>
                <field name="start_date" invisible="1"/>
                <field name="end_date" invisible="1"/>
                <field name="artifact_ids" widget="call_debrief" options="{'callStartDateField': 'start_date', 'callEndDateField': 'end_date'}"/>
            </form>
        `,
    });
}

test("CallDebrief: transcript only interactions", async () => {
    const pyEnv = await startServer();
    const testRecordId = pyEnv["test.call.record"].create({
        start_date: "2023-01-01 10:00:00",
        end_date: "2023-01-01 10:00:10",
        artifact_ids: [
            pyEnv["mail.call.artifact"].create({
                transcript: "1\n00:00:01,000 --> 00:00:03,000\nHello world",
                is_stt: true,
                start_ms: 0,
                end_ms: 10000,
            }),
        ],
    });
    await start();
    await _openDebriefView(pyEnv, testRecordId);

    expect(".o-CallDebrief-media-container").toHaveClass("o-CallDebrief-media-container--no-video");

    const line = queryOne("p[data-timestamp]");
    await click(line);
    await animationFrame();
    expect(".o-CallDebriefTimeline-timestamp").toHaveText("00:01");
});

test("CallDebrief: transcript gap detection", async () => {
    const pyEnv = await startServer();
    const testRecordId = pyEnv["test.call.record"].create({
        start_date: "2023-01-01 10:00:00",
        end_date: "2023-01-01 10:00:20",
        artifact_ids: [
            pyEnv["mail.call.artifact"].create({
                transcript:
                    "1\n00:00:01,000 --> 00:00:03,000\nHello\n\n2\n00:00:08,000 --> 00:00:10,000\nWorld",
                is_stt: true,
                start_ms: 0,
                end_ms: 20000,
            }),
        ],
    });
    await start();
    await _openDebriefView(pyEnv, testRecordId);

    const gaps = queryAll(".o-CallDebrief-transcript-gap");
    expect(gaps).toHaveCount(1, { message: "Should detect exactly one gap." });

    // Gap should represent the 5s difference between 00:03 and 00:08
    expect(gaps[0]).toHaveText("silence (00:05)");

    const lines = queryAll("p[data-timestamp]");
    expect(lines).toHaveCount(2, { message: "Should render both spoken lines." });
});

test("CallDebrief: renders video and transcript with playback", async () => {
    _setupCallDebriefPatch();

    const pyEnv = await startServer();

    const transcriptSourceId = pyEnv["ir.attachment"].create({
        name: "transcription_source.ogg",
        mimetype: "audio/ogg",
    });
    const transcriptId = pyEnv["mail.call.artifact"].create({
        transcript: "1\n00:00:01,000 --> 00:00:03,000\nHello world",
        is_stt: true,
        media_id: transcriptSourceId,
        start_ms: 0,
        end_ms: 60000,
    });

    const videoId = _createRecording(pyEnv, { start: 0, type: "video" });

    const testRecordId = pyEnv["test.call.record"].create({
        start_date: "2023-01-01 10:00:00",
        end_date: "2023-01-01 10:01:00", // 60s call
        artifact_ids: [transcriptId, videoId],
    });

    await start();
    await _openDebriefView(pyEnv, testRecordId);

    expect(".o-CallDebrief-media-container").not.toHaveClass(
        "o-CallDebrief-media-container--no-video"
    );
    await contains(".o-CallDebrief-video video");
    await contains("audio", { count: 0 });
    await contains(".o-CallDebrief-transcript-text", { text: "Hello world" });

    // Mute first to avoid noise
    await click("button.o-CallDebrief-muteBtn");

    // Start playback
    const video = queryOne("video");
    const playingPromise = new Promise((r) => video.addEventListener("playing", r, { once: true }));
    await click("[data-icon='play_arrow']");
    await animationFrame();
    expect("[data-icon='pause']").toHaveCount(1);

    // Wait for actual playback to start before pausing
    await playingPromise;

    // Stop playback to avoid AbortError when the test destroys the video element
    await click("[data-icon='pause']");
    await animationFrame();
});

test("CallDebrief: timeline-transcript-media synchronization", async () => {
    _setupCallDebriefPatch();
    const pyEnv = await startServer();

    // Create 3 segments of 60s each = 180s total duration
    const art1 = _createRecording(pyEnv, { start: 0, type: "audio" });
    const art2 = _createRecording(pyEnv, { start: 60, type: "audio" });
    const art3 = _createRecording(pyEnv, { start: 120, type: "audio" });

    // Transcripts associated with each segment time range
    const trans1 = pyEnv["mail.call.artifact"].create({
        transcript: "1\n00:00:05,000 --> 00:00:08,000\nSegment 1 Text",
        is_stt: true,
        start_ms: 0,
        end_ms: 60000,
    });
    const trans2 = pyEnv["mail.call.artifact"].create({
        // Relative 2s -> Global 62s
        transcript: "1\n00:00:02,000 --> 00:00:04,000\nSegment 2 Text",
        is_stt: true,
        start_ms: 60000,
        end_ms: 120000,
    });
    const trans3 = pyEnv["mail.call.artifact"].create({
        // Relative 5s -> Global 125s
        transcript: "1\n00:00:05,000 --> 00:00:07,000\nSegment 3 Text",
        is_stt: true,
        start_ms: 120000,
        end_ms: 180000,
    });

    const testRecordId = pyEnv["test.call.record"].create({
        start_date: "2023-01-01 10:00:00",
        end_date: "2023-01-01 10:03:00",
        artifact_ids: [art1, trans1, art2, trans2, art3, trans3],
    });

    await start();
    await _openDebriefView(pyEnv, testRecordId);
    await animationFrame();

    // Ensure Segment 1's initial audio element is loaded before we click or interact with it
    const initialAudio = queryOne("audio");
    if (
        initialAudio &&
        [HTMLMediaElement.HAVE_NOTHING, HTMLMediaElement.HAVE_METADATA].includes(
            initialAudio.readyState
        )
    ) {
        await new Promise((r) => initialAudio.addEventListener("loadeddata", r, { once: true }));
    }

    const lines = queryAll("p[data-timestamp]");

    // Select transcript line -> Adjusts playhead and audio
    await click(lines[0]);
    await animationFrame();
    expect(".o-CallDebriefTimeline-timestamp").toHaveText("00:05");
    expect(lines[0]).toHaveClass("o-CallDebrief-transcript-highlight");
    const audioTime1 = queryOne("audio").currentTime;
    expect(Math.abs(audioTime1 - 5) <= 1).toBe(true, {
        message: `Audio currentTime should be close to 5s, but was ${audioTime1}`,
    });

    // Fire timeupdate to clear the skipNextTimeUpdate flag that was set by the line click
    queryOne("audio").dispatchEvent(new Event("timeupdate"));

    // Move playhead -> Seeks audio and scroll to nearest transcript line
    // Clicking the timeline defaults to center (50%). Total duration 180s -> 90s (01:30).
    await click(".o-CallDebriefTimeline");
    await animationFrame();

    const timestampText = queryOne(".o-CallDebriefTimeline-timestamp").innerText;
    const [minutes, seconds] = timestampText.split(":").map(Number);
    const totalSeconds = minutes * 60 + seconds;
    expect(Math.abs(totalSeconds - 90) <= 2).toBe(true, {
        message: `Playhead should move close to 90s (01:30), but was ${timestampText}`,
    });
    // 90s is closer to Segment 2 (62s) than Segment 3 (125s)
    expect(lines[1]).toHaveClass("o-CallDebrief-transcript-highlight");
    // Global 90s is 30s relative to Segment 2 (starts at 60s)
    const audioTime2 = queryOne("audio").currentTime;
    expect(Math.abs(audioTime2 - 30) <= 1).toBe(true, {
        message: `Audio currentTime should be close to 30s, but was ${audioTime2}`,
    });

    // Media timestamp change (simulates playing) -> Updates playhead position and transcript highlight
    const audio = queryOne("audio");
    audio.currentTime = 6;
    // Wait for the seek to complete so the `seeking` flag becomes false, otherwise onTimeUpdate skips the event
    await new Promise((r) => audio.addEventListener("seeked", r, { once: true }));
    audio.dispatchEvent(new Event("timeupdate"));
    await animationFrame();
    const finalTimestampText = queryOne(
        ".o-CallDebriefMediaControls-timeLabel .o_current_time"
    ).innerText;
    const [finalM, finalS] = finalTimestampText.split(":").map(Number);
    const finalTotalSeconds = finalM * 60 + finalS;
    // Segment 2 starts at 60s, so 60 + 6 = 66s (01:06)
    expect(Math.abs(finalTotalSeconds - 66) <= 1).toBe(true, {
        message: `Timestamp should be close to 66s (01:06), but was ${finalTimestampText}`,
    });
    // Global 66s is within Segment 2, so the second transcript line (starts at 62s) should be highlighted
    expect(lines[1]).toHaveClass("o-CallDebrief-transcript-highlight");
});

test("CallDebrief: skips STT artifacts from playable segments", async () => {
    _setupCallDebriefPatch();
    const pyEnv = await startServer();

    // Create 1 standard audio recording and 1 parallel pending STT artifact (both covering 0s to 60s)
    const audioId = _createRecording(pyEnv, { start: 0, type: "audio" });
    const transcriptAttachmentId = pyEnv["ir.attachment"].create({
        name: "stt_audio.webm",
        mimetype: "audio/webm",
    });
    const transcriptId = pyEnv["mail.call.artifact"].create({
        media_id: transcriptAttachmentId,
        transcript: "1\n00:00:01,000 --> 00:00:03,000\nHello world",
        is_stt: true,
        start_ms: 0,
        end_ms: 60000,
    });

    const testRecordId = pyEnv["test.call.record"].create({
        start_date: "2023-01-01 10:00:00",
        end_date: "2023-01-01 10:01:00", // 60s call
        artifact_ids: [audioId, transcriptId],
    });

    await start();
    await _openDebriefView(pyEnv, testRecordId);
    await animationFrame();

    // The STT artifact must be skipped from the timeline (only 1 media segment should be rendered)
    expect(".o-CallDebriefTimeline-media-segment").toHaveCount(1, {
        message: "Only the standard recording should be rendered on the timeline, not the STT artifact.",
    });

    // The transcript itself must still load and render correctly
    expect("p[data-timestamp]").toHaveCount(1, {
        message: "The transcript should still render correctly.",
    });
});

test("CallDebrief: skips pending media without hiding its transcript", async () => {
    const pyEnv = await startServer();
    const mediaId = _createRecording(pyEnv, { type: "video" });
    pyEnv["mail.call.artifact"].write([mediaId], { recording_upload_pending: true });
    const transcriptId = pyEnv["mail.call.artifact"].create({
        transcript: "1\n00:00:01,000 --> 00:00:03,000\nHello world",
        is_stt: true,
        start_ms: 0,
        end_ms: 60000,
    });
    const testRecordId = pyEnv["test.call.record"].create({
        start_date: "2023-01-01 10:00:00",
        end_date: "2023-01-01 10:01:00",
        artifact_ids: [mediaId, transcriptId],
    });
    await start();
    await _openDebriefView(pyEnv, testRecordId);
    await contains(".o-CallDebrief-transcript-text", { text: "Hello world" });
    await contains(".o-CallDebriefTimeline-media-segment", { count: 0 });
    await contains("video, audio", { count: 0 });
});
