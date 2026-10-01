const callbacks = [];

/** Listen for replies captured by the mocked IAP submission. */
export function setupAIResults(trigger = ".o-mail-ChatWindow") {
    return {
        content: "Listen for mocked IAP results",
        trigger,
        async run() {
            callbacks.length = 0;
            const busService = odoo.__WOWL_DEBUG__.root.env.services.bus_service;
            // Each tour subscribes once and closes its browser afterward, so no manual unsubscribe is needed.
            busService.subscribe("ai.test/callbacks_ready", (callback) => {
                callbacks.push(callback);
            });
            await busService.start();
        },
    };
}

/** Deliver this round's mocked callbacks, including its optional chat-title reply. */
export function deliverAIResults() {
    return {
        content: "Deliver the mocked IAP results for this round",
        trigger: "body",
        async run({ waitUntil }) {
            await waitUntil(() => callbacks.length > 0);
            const batch = callbacks.splice(0);
            for (const callback of batch) {
                const response = await fetch("/ai/completion_result_ready", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(callback),
                });
                if (!response.ok) {
                    throw new Error(await response.text());
                }
            }
        },
    };
}
