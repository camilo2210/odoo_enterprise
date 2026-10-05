/* eslint-env serviceworker */
/* eslint-disable no-restricted-globals */

/**
 * When a push subscription is lost, expires, or becomes invalid, the service
 * worker receives a `pushsubscriptionchange` event. When this event is triggered,
 * we retrieve the new subscription details and send the updated endpoint and
 * keys to the server.
 */
self.addEventListener("pushsubscriptionchange", event => {
    const subscription = self.registration.pushManager
        .subscribe(event.oldSubscription.options)
        .then(subscription => {
            const pushDeviceConfig = subscription.toJSON();
            return fetch("/social_push_notifications/save_push_subscription", {
                headers: {
                    "Content-type": "application/json",
                },
                body: JSON.stringify({
                    id: 1,
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        endpoint: pushDeviceConfig.endpoint,
                        keys: pushDeviceConfig.keys,
                    }
                }),
                method: "POST",
                mode: "cors",
                credentials: "include",
            });
        });
    event.waitUntil(subscription);
});

self.addEventListener("notificationclick", event => {
    event.notification.close();
    const url = event.notification.data?.url;
    if (!url) {
        return;
    }
    event.waitUntil(
        clients
            .matchAll({ type: "window" })
            .then(clientList => {
                for (const client of clientList) {
                    if (client.url === url && "focus" in client) {
                        return client.focus();
                    }
                }
                if (clients.openWindow) {
                    return clients.openWindow(url);
                }
            })
    );
});

self.addEventListener("push", event => {
    const payload = event.data?.json() ?? {};
    if (!payload.title) {
        return;
    }
    const options = {};
    if (payload.body) {
        options.body = payload.body;
    }
    if (payload.icon) {
        options.icon = payload.icon;
    }
    if (payload.target_url) {
        options.data = { url: payload.target_url.trim() };
    }
    event.waitUntil(self.registration.showNotification(payload.title, options));
});
