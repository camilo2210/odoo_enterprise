/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { VoipAudioBinaryField } from "@voip/widgets/audio_binary/audio_binary_field";
import { allowTranslations } from "@web/../tests/web_test_helpers";

test.tags("headless");

describe("VoipAudioBinaryField", () => {
    test("uploading audio selects the upload source and clears the TTS text", async () => {
        const updates = [];
        const field = {
            setPreview: VoipAudioBinaryField.prototype.setPreview,
            state: { previewSrc: false },
            props: {
                fileNameField: "data_filename",
                name: "data",
                record: {
                    update(values) {
                        updates.push(values);
                    },
                },
            },
        };

        await VoipAudioBinaryField.prototype.update.call(field, {
            data: "UklGRg==",
            name: "welcome.wav",
        });

        expect(updates).toEqual([
            {
                data: { filename: "welcome.wav", content: "UklGRg==" },
                data_filename: "welcome.wav",
                source_type: "upload",
                tts_text: false,
            },
        ]);
        expect(field.state.previewSrc).toBe("data:audio/wav;base64,UklGRg==");
    });

    test("pending audio is playable before the record is saved", () => {
        const field = {
            state: { previewSrc: "data:audio/wav;base64,UklGRg==" },
            props: {
                name: "data",
                record: {
                    data: { data: "4.2 KB" },
                    dirty: false,
                    resId: 42,
                },
            },
        };
        const getAudioSrc = Object.getOwnPropertyDescriptor(
            VoipAudioBinaryField.prototype,
            "audioSrc"
        ).get;
        const getCanPlay = Object.getOwnPropertyDescriptor(
            VoipAudioBinaryField.prototype,
            "canPlay"
        ).get;
        Object.defineProperty(field, "audioSrc", { get: () => getAudioSrc.call(field) });

        expect(getCanPlay.call(field)).toBe(true);
        expect(field.audioSrc).toBe("data:audio/wav;base64,UklGRg==");
    });

    test("generated TTS audio replaces the current preview", () => {
        const field = { state: { previewSrc: "data:audio/wav;base64,b2xk" } };

        VoipAudioBinaryField.prototype.setPreview.call(field, "UklGRg==");

        expect(field.state.previewSrc).toBe("data:audio/wav;base64,UklGRg==");
    });

    test("delegated audio uses the related sound id", () => {
        const field = {
            state: { previewSrc: false },
            props: {
                audioRecordField: "menu_sound_id",
                name: "data",
                record: {
                    data: {
                        data: "4.2 KB",
                        data_version: 3,
                        menu_sound_id: { id: 73 },
                    },
                    dirty: false,
                    resId: 42,
                },
            },
        };
        const getAudioSrc = Object.getOwnPropertyDescriptor(
            VoipAudioBinaryField.prototype,
            "audioSrc"
        ).get;

        expect(getAudioSrc.call(field)).toBe("/voip/audio/message/73?v=3");
    });

    test("dropping a WAV file updates the audio draft", async () => {
        const updates = [];
        const field = {
            notification: { add() {} },
            state: { isDragging: true },
            update(values) {
                updates.push(values);
            },
        };
        const file = new File(["audio"], "welcome.wav", { type: "audio/wav" });

        await VoipAudioBinaryField.prototype.onDrop.call(field, {
            dataTransfer: { files: [file] },
        });

        expect(field.state.isDragging).toBe(false);
        expect(updates).toHaveLength(1);
        expect(updates[0].name).toBe("welcome.wav");
        expect(updates[0].data).toBe("YXVkaW8=");
    });

    test("dropping another file type is rejected", async () => {
        allowTranslations();
        const notifications = [];
        const field = {
            notification: { add: (...args) => notifications.push(args) },
            state: { isDragging: true },
            update() {
                throw new Error("The file should not be accepted");
            },
        };
        const file = new File(["audio"], "welcome.mp3", { type: "audio/mpeg" });

        await VoipAudioBinaryField.prototype.onDrop.call(field, {
            dataTransfer: { files: [file] },
        });

        expect(notifications).toHaveLength(1);
        expect(String(notifications[0][0])).toBe("Upload a WAV file.");
        expect(notifications[0][1]).toEqual({ type: "danger" });
    });
});
