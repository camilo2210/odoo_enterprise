import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { Interaction } from "@web/public/interaction";
import { browser } from "@web/core/browser/browser";
import { PushNotificationRequest } from "@social_push_notifications/components/push_notification_request/push_notification_request";
import { useListener } from "@odoo/owl";

const mainComponents = registry.category("main_components");

/**
 * The following interaction is responsible for automatically displaying the
 * push notification request popup whenever the #wrapwrap container is present
 * in the DOM. It also handles the creation of the service worker registration
 * that allows users to receive push notifications.
 */
export class PushNotificationRequestInteraction extends Interaction {
    static selector = "#wrapwrap";

    setup() {
        // Unregister the service worker when the user disables the notifications:
        browser.navigator.permissions.query({
            name: "notifications",
        }).then(permissionStatus => {
            permissionStatus.addEventListener("change", async event => {
                const permission = event.target.state;
                if (permission !== "granted") {
                    const registration = await this.getServiceWorkerRegistration("/");
                    registration?.unregister();
                    browser.localStorage.removeItem("social_push_notifications.last_sync");
                }
            });
        });

        useListener(this.env.bus,
            "SOCIAL_PUSH_NOTIFICATIONS:SHOW_PUSH_NOTIFICATION_REQUEST",
            /** @param {Event} event */
            async event => {
                const permission = browser.Notification?.permission;
                if (permission !== "denied" && !(await this.getPushSubscription())) {
                    const config = event.detail || await this.fetchNotificationRequestConfig();
                    await this.openNotificationRequest(config);
                }
            });
    }

    /** @override */
    async willStart() {
        // Unregister the legacy service worker registration:
        const registration = await this.getServiceWorkerRegistration("/social_push_notifications/static/src/js/");
        registration?.unregister();

        const getElapsedDaysSince = date => {
            return luxon.DateTime.fromISO(date).until(luxon.DateTime.now()).length("days");
        };

        // Occasionally verify that the server has the user's endpoint and associated keys:
        const lastSync = browser.localStorage.getItem("social_push_notifications.last_sync");
        if (!lastSync || getElapsedDaysSince(lastSync) > 7) {
            const registration = await this.getServiceWorkerRegistration("/");
            if (registration) {
                const subscription = await this.getPushSubscription(registration);
                if (subscription) {
                    const data = subscription.toJSON();
                    let isPushSubscriptionRegistered = true;
                    try {
                        isPushSubscriptionRegistered = await rpc(
                            "/social_push_notifications/is_push_subscription_registered", {
                                endpoint: data.endpoint,
                                keys: data.keys,
                            });
                        if (isPushSubscriptionRegistered) {
                            const now = luxon.DateTime.now().toISO();
                            browser.localStorage.setItem("social_push_notifications.last_sync", now);
                        }
                    } catch {};
                    if (!isPushSubscriptionRegistered) {
                        registration.unregister();
                        browser.localStorage.removeItem("social_push_notifications.last_sync");
                    }
                }
            }
        }

        // Unregister the service worker registration if the notifications are denied:
        const permission = browser.Notification?.permission;
        if (permission === "denied") {
            const registration = await this.getServiceWorkerRegistration("/");
            registration?.unregister();
            browser.localStorage.removeItem("social_push_notifications.last_sync");
            return;
        }

        // Automatically show the push notification request popup:
        const rejectionDate = browser.localStorage.getItem("social_push_notifications.rejection_date");
        if ((!rejectionDate || getElapsedDaysSince(rejectionDate) > 7) && !(await this.getPushSubscription())) {
            const config = await this.fetchNotificationRequestConfig();
            this.openNotificationRequest(config);
        }
    }

    /** @param {Object} config */
    async openNotificationRequest(config) {
        browser.setTimeout(() => {
            const key = "social_push_notifications.push_notification_request";
            if (mainComponents.get(key, false)) {
                return;
            }
            const closePopup = () => {
                mainComponents.remove(key);
            };
            mainComponents.add(
                "social_push_notifications.push_notification_request", {
                Component: PushNotificationRequest,
                props: {
                    config,
                    onAllowPushNotifications: async () => {
                        closePopup();
                        try {
                            await this.enablePushNotifications();
                            const now = luxon.DateTime.now().toISO();
                            browser.localStorage.setItem("social_push_notifications.last_sync", now);
                        } catch (error) {
                            const registration = await this.getServiceWorkerRegistration("/");
                            registration?.unregister();
                            browser.localStorage.removeItem("social_push_notifications.last_sync");
                            this.services.notification.add(error.message, {
                                title: _t("Failed to enable push notifications"),
                                type: "danger",
                                sticky: true,
                            });
                        }
                    },
                    onDenyPushNotifications: () => {
                        closePopup();
                        const now = luxon.DateTime.now().toISO();
                        browser.localStorage.setItem("social_push_notifications.rejection_date", now);
                    },
                    close: closePopup,
                }
            });
        }, 1000 * (config.delay || 0));
    }

    async enablePushNotifications() {
        const permission = await browser.Notification.requestPermission();
        if (permission !== "granted") {
            throw new Error(permission === "denied"
                ? _t("It looks like notifications are blocked by your browser. To stay updated, please enable them in your browser settings!")
                : _t("It looks like notifications aren't enabled in your browser. To stay updated, please enable them in your browser settings!"));
        }

        let registration = await this.getServiceWorkerRegistration("/");
        registration?.unregister();

        const url = new URL("/social_push_notifications/service_worker.js", window.location.origin);
        registration = await browser.navigator.serviceWorker.register(url, { scope: "/" });

        const key = await rpc("/social_push_notifications/get_vapid_public_key");
        const applicationServerKey = Uint8Array.from(
            atob(key.replace(/-/g, "+")
                    .replace(/_/g, "/")
                    .padEnd(Math.ceil(key.length / 4) * 4, "=")),
            c => c.charCodeAt(0));

        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey,
        });

        const data = subscription.toJSON();
        await rpc("/social_push_notifications/save_push_subscription", {
            endpoint: data.endpoint,
            keys: data.keys,
        });
    }

    /** @returns {Object} */
    async fetchNotificationRequestConfig() {
        const response = await fetch("/social_push_notifications/get_notification_request_config");
        return await response.json();
    }

    /**
     * @param {string} scope
     * @returns {ServiceWorkerRegistration}
     */
    async getServiceWorkerRegistration(scope) {
        const url = new URL(scope, window.location.origin);
        const registrations = await browser.navigator.serviceWorker.getRegistrations();
        return registrations.find(registration => registration.scope === url.toString());
    }

    /**
     * @param {ServiceWorkerRegistration} [registration]
     * @returns {PushSubscription}
     */
    async getPushSubscription(registration) {
        registration = registration || await this.getServiceWorkerRegistration("/");
        if (registration) {
            const pushManager = registration.pushManager;
            return await pushManager.getSubscription();
        }
    }
};

registry.category("public.interactions").add(
    "social_push_notifications.notification_manager",
    PushNotificationRequestInteraction
);
