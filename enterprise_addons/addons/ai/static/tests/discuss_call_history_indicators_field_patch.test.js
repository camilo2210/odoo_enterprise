import {
    contains,
    mailModels,
    openListView,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";

import { describe, test } from "@odoo/hoot";
import { defineModels, fields } from "@web/../tests/web_test_helpers";

import "@ai/views/fields/discuss_call_history_indicators/discuss_call_history_indicators_field_patch";

describe.current.tags("desktop", "discuss_call_history");

class DiscussCallHistory extends mailModels.DiscussCallHistory {
    has_transcript = fields.Boolean();
}

defineModels({ ...mailModels, DiscussCallHistory });

test("recording indicators include the transcript", async () => {
    const pyEnv = await startServer();
    pyEnv["discuss.call.history"].create({
        has_audio: true,
        has_recording: true,
        has_transcript: true,
    });
    pyEnv["discuss.call.history"].create({
        has_audio: true,
        has_recording: true,
    });
    await start();
    await openListView("discuss.call.history", {
        arch: `
            <list>
                <field name="has_recording" widget="discuss_call_history_indicators"/>
            </list>
        `,
    });
    await contains("[data-icon='volume_up']", { count: 2 });
    await contains("[data-icon='subtitles']");
    await contains("[data-icon='volume_up']:not(.ms-1)", { count: 2 });
    await contains("[data-icon='subtitles'].ms-1");
});

test("transcript-only recordings show only the transcript indicator", async () => {
    const pyEnv = await startServer();
    pyEnv["discuss.call.history"].create({
        has_recording: true,
        has_transcript: true,
    });
    await start();
    await openListView("discuss.call.history", {
        arch: `
            <list>
                <field name="has_recording" widget="discuss_call_history_indicators"/>
            </list>
        `,
    });
    await contains("[data-icon='subtitles']");
    await contains("[data-icon='movie']", { count: 0 });
    await contains("[data-icon='volume_up']", { count: 0 });
});

test("recording indicators respect the field value", async () => {
    const pyEnv = await startServer();
    pyEnv["discuss.call.history"].create({
        has_audio: true,
        has_recording: false,
        has_video: true,
    });
    await start();
    await openListView("discuss.call.history", {
        arch: `
            <list>
                <field name="has_recording" widget="discuss_call_history_indicators"/>
            </list>
        `,
    });
    await contains(".o_list_view");
    await contains("[data-icon='movie']", { count: 0 });
    await contains("[data-icon='volume_up']", { count: 0 });
    await contains("[data-icon='subtitles']", { count: 0 });
});
