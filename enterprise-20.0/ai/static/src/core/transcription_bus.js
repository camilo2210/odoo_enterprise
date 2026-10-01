import { EventBus } from "@odoo/owl";

export const AITranscriptionEvent = {
    AUDIO_PROCESSOR_DATA: "AUDIO_PROCESSOR_DATA",
    AUDIO_PROCESSOR_STATE: "AUDIO_PROCESSOR_STATE",
    AUDIO_PROCESSOR_FREQUENCY: "AUDIO_PROCESSOR_FREQUENCY",
    REALTIME_CLIENT_MESSAGE: "REALTIME_CLIENT_MESSAGE",
};

export const transcriptionBus = new EventBus();
