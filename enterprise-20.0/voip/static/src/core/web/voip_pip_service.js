import { effect, proxy } from "@odoo/owl";

import { VoipPipWindow } from "@voip/core/web/voip_pip_window";
import { browser } from "@web/core/browser/browser";
import { isMobileOS } from "@web/core/browser/feature_detection";
import { registry } from "@web/core/registry";

export const voipPipService = {
    dependencies: ["mail.popout", "voip"],

    start(_env, services) {
        const sizes = {
            compact: { width: 280, height: 138 },
            keypad: { width: 280, height: 352 },
        };
        const voip = services.voip;
        const state = proxy({
            active: false,
        });
        let pipWindow = null;
        let isMediaSessionHandlerRegistered = false;
        let hadActiveCall = false;

        if (!voip.bus) {
            return proxy({
                state,
                close() {},
                async open() {
                    return null;
                },
                setSize() {},
                get isSupported() {
                    return false;
                },
                get pipWindow() {
                    return pipWindow;
                },
            });
        }

        const popoutService = services["mail.popout"];
        const popout = popoutService.createManager(Symbol("voip.pip"));
        popout.addHooks(
            () => {},
            () => {
                state.active = false;
                pipWindow = null;
                if (voip.userAgent.frontSession?.isInProgress) {
                    voip.softphone.show();
                }
            }
        );
        voip.bus.addEventListener("session_changed", () => {
            const hasActiveCall = hasInProgressCall();
            if (hasActiveCall && !hadActiveCall) {
                registerMediaSessionHandler();
            } else if (!hasActiveCall && hadActiveCall) {
                clearMediaSessionHandler();
                close();
            }
            hadActiveCall = hasActiveCall;
        });

        async function open() {
            if (!hasInProgressCall()) {
                return null;
            }
            state.active = true;
            try {
                const openedWindow = await popout.pip(VoipPipWindow, {
                    props: {},
                    options: {
                        ...sizes.compact,
                        useAlternativeAssets: true,
                    },
                });
                if (!hasInProgressCall()) {
                    openedWindow.close();
                    state.active = false;
                    return null;
                }
                pipWindow = openedWindow;
                pipWindow.document.body.style.margin = "0";
                return pipWindow;
            } catch (error) {
                state.active = false;
                pipWindow = null;
                throw error;
            }
        }

        function close() {
            state.active = false;
            pipWindow?.close();
            pipWindow = null;
        }

        function setSize({ width, height }) {
            if (!pipWindow || pipWindow.closed || !pipWindow.resizeTo) {
                return;
            }
            pipWindow.resizeTo(width, height);
        }

        function hasInProgressCall() {
            return Object.values(voip.userAgent.sessions).some((session) => session.isInProgress);
        }

        function registerMediaSessionHandler() {
            if (isMediaSessionHandlerRegistered || voip.store.rtc?.selfSession) {
                return;
            }
            try {
                browser.navigator.mediaSession.setActionHandler(
                    "enterpictureinpicture",
                    async ({ enterPictureInPictureReason }) => {
                        if (
                            enterPictureInPictureReason !== "contentoccluded" ||
                            !hasInProgressCall() ||
                            state.active
                        ) {
                            return;
                        }
                        try {
                            const openedWindow = await service.open();
                            if (openedWindow) {
                                voip.softphone.hide();
                            }
                        } catch {
                            // Picture-in-picture is optional and may be unavailable at runtime.
                        }
                    }
                );
                isMediaSessionHandlerRegistered = true;
            } catch {
                // "enterpictureinpicture" is not universally available.
            }
        }

        function clearMediaSessionHandler() {
            if (!isMediaSessionHandlerRegistered) {
                return;
            }
            if (!voip.store.rtc?.selfSession) {
                try {
                    browser.navigator.mediaSession.setActionHandler("enterpictureinpicture", null);
                } catch {
                    // The handler may have become unsupported since registration.
                }
            }
            isMediaSessionHandlerRegistered = false;
        }

        const service = proxy({
            state,
            close,
            open,
            setSize,
            sizes,
            get isSupported() {
                return !isMobileOS() && Boolean(window.documentPictureInPicture || window.open);
            },
            get pipWindow() {
                return pipWindow;
            },
        });
        effect(() => {
            if (voip.store.rtc?.selfSession) {
                // Discuss owns the single MediaSession PiP action while its call is active.
                isMediaSessionHandlerRegistered = false;
            } else if (hasInProgressCall()) {
                registerMediaSessionHandler();
            }
        });
        return service;
    },
};

registry.category("services").add("voip.pip", voipPipService);
