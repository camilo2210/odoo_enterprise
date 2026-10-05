import { router } from "@web/core/browser/router";
import { patch } from "@web/core/utils/patch";
import AudioProcessor from "./audio/audio_processor";
import RealtimeClient from "./realtime_client";

patch(router, {
    pushState() {
        super.pushState(...arguments);
        const audioProcessor = AudioProcessor.getInstance();
        const realtimeClient = RealtimeClient.getInstance();

        audioProcessor?.stop();
        realtimeClient?.disconnect();
    },
});
