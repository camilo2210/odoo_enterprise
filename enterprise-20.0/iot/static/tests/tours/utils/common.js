import { browser } from "@web/core/browser/browser";

/**
 * Browser can be killed before the IoT request (longpolling, websocket, ...)
 * has been performed. This step adds a 1s delay
 */
export function waitForIotRequest(delay = 1000) {
    return {
        trigger: "body",
        run: async () => {
            await new Promise((resolve) => setTimeout(resolve, delay));
        },
    };
}

/**
 * Mock the browser request to /iot_drivers/action depending on the
 * provided cookie's value (``iot_test``)
 * The goal is to test the behavior when the IoT Box isn't reachable
 * on the localnetwork.
 */
export function mockIotActionRequest() {
    return {
        trigger: "body",
        run: async () => {
            const iotTest = document.cookie
                .split("; ")
                .find((r) => r.startsWith("iot_test="))
                ?.split("=")[1];

            if (iotTest) {
                const originalFetch = browser.fetch;
                browser.fetch = async (url, options) => {
                    if (url.includes("/iot_drivers/action")) {
                        if (iotTest === "ws") {
                            throw new Error("IoT Longpolling is mocked");
                        }
                        if (iotTest === "lp") {
                            const body = () => {
                                try {
                                    return JSON.parse(options?.body ?? "{}");
                                } catch {
                                    return options.body;
                                }
                            };

                            return new Response(
                                JSON.stringify({
                                    result: {
                                        ...body(),
                                        status: "success",
                                        result: {},
                                    },
                                })
                            );
                        }
                    }
                    return originalFetch(url, options);
                };
            }
        },
    };
}

export function openTestShopIotBox() {
    return {
        content: "Click on 'Test Shop' IoT Box",
        trigger: ".o_kanban_record:contains('Test Shop')",
        run: "click",
    };
}
