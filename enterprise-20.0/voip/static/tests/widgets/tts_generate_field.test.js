import { expect, test } from "@odoo/hoot";

import { TtsGenerateField } from "@voip/widgets/tts_generate/tts_generate_field";

test("a generated preview does not overwrite text edited during generation", async () => {
    const rpc = Promise.withResolvers();
    const notifications = [];
    const busEvents = [];
    const updates = [];
    const container = document.createElement("div");
    container.className = "o-voip-SoundForm-tts";
    const textarea = document.createElement("textarea");
    textarea.value = "Initial text";
    const button = document.createElement("button");
    container.append(textarea, button);
    const field = {
        notification: {
            add(message, options) {
                notifications.push({ message, options });
            },
        },
        orm: { call: () => rpc.promise },
        props: {
            record: {
                data: { name: "Greeting", tts_voice: "voice-a" },
                model: { bus: { trigger: (...args) => busEvents.push(args) } },
                update(values) {
                    updates.push(values);
                },
            },
        },
        state: { isGenerating: false },
    };

    const generation = TtsGenerateField.prototype.generateAudio.call(field, {
        currentTarget: button,
    });
    textarea.value = "Edited text";
    rpc.resolve({
        content: "UklGRg==",
        filename: "greeting.wav",
        text: "Initial text",
        voice: "voice-a",
    });
    await generation;

    expect(updates).toEqual([]);
    expect(busEvents).toEqual([]);
    expect(notifications).toHaveLength(1);
    expect(notifications[0].options.type).toBe("warning");
    expect(field.state.isGenerating).toBe(false);
});

test("a generated audio is forwarded to the audio preview", async () => {
    const busEvents = [];
    const container = document.createElement("div");
    container.className = "o-voip-SoundForm-tts";
    const textarea = document.createElement("textarea");
    textarea.value = "New text";
    const button = document.createElement("button");
    container.append(textarea, button);
    const record = {
        data: { name: "Greeting", tts_voice: "voice-a" },
        model: { bus: { trigger: (...args) => busEvents.push(args) } },
        update() {},
    };
    const field = {
        notification: { add() {} },
        orm: {
            call: () => ({
                content: "UklGRg==",
                filename: "greeting.wav",
                text: "New text",
                voice: "voice-a",
            }),
        },
        props: { record },
        state: { isGenerating: false },
    };

    await TtsGenerateField.prototype.generateAudio.call(field, { currentTarget: button });

    expect(busEvents).toEqual([["VOIP:TTS-AUDIO-PREVIEW", { content: "UklGRg==", record }]]);
});
