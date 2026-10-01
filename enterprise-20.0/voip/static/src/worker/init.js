/* eslint-disable no-restricted-globals */
/* eslint-env worker */

import { VoipWorker } from "./voip_worker";

const voipWorker = new VoipWorker();

// if self is a SharedWorker:
if (self.name.includes("shared")) {
    self.addEventListener("connect", (ev) => {
        const client = ev.ports[0];
        client.addEventListener("message", voipWorker.handleMessage.bind(voipWorker));
        client.start();
    });
}
// if self is a Worker:
else {
    self.addEventListener("message", voipWorker.handleMessage.bind(voipWorker));
}
