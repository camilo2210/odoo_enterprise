import { HookEventBus } from "@web_mobile/js/hook_event_bus";
import { Plugin, usePlugin } from "@odoo/owl";
import { services } from "@web/core/services";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

import mobile from "@web_mobile/js/services/core";
import { shortcutItem, switchAccountItem } from "./user_menu_items";

const userMenuRegistry = registry.category("user_menuitems");

export class MobilePlugin extends Plugin {
    /** @private */
    timeBetweenReadsInMs = session.time_between_reads_in_ms || 100;
    /** @private */
    idInterval = null;

    setup() {
        let listenerCount = 0;
        this.bus = new HookEventBus({
            onAddListener: (eventName, listener) => {
                listenerCount++;
                if (listenerCount === 1) {
                    this.enableReader();
                }
            },
            onRemoveListener: (eventName, listener) => {
                listenerCount--;
                if (listenerCount === 0) {
                    this.stopReader();
                }
            },
        });

        if (mobile.methods.addHomeShortcut) {
            userMenuRegistry.add("web_mobile.shortcut", shortcutItem);
        }

        if (mobile.methods.switchAccount) {
            // remove "Log Out" and "My Odoo.com Account"
            userMenuRegistry.remove("log_out");
            userMenuRegistry.remove("odoo_account");

            userMenuRegistry.add("web_mobile.switch", switchAccountItem);
        }
    }

    enableReader() {
        if (mobile.methods.enableReader && mobile.methods.getReaderData) {
            mobile.methods.enableReader().catch((e) => console.error(e));
            if (!this.idInterval) {
                this.idInterval = setInterval(async () => {
                    try {
                        const value = await mobile.methods.getReaderData();
                        if (value.success) {
                            const data = value.data;
                            if (data.length > 0) {
                                this.bus.trigger("mobile_reader_scanned", { data });
                            }
                        }
                    } catch (e) {
                        console.error(e);
                    }
                }, this.timeBetweenReadsInMs);
            }
        }
    }

    stopReader() {
        if (this.idInterval) {
            clearInterval(this.idInterval);
            this.idInterval = null;
        }
    }
}

services.add(MobilePlugin);

/**
 * -----------------------------------------------------------------------------
 * @todo owl3 migration
 * temporary - to remove when all use of the mobile service are removed
 * -----------------------------------------------------------------------------
 */
registry.category("services").add("mobile", {
    start() {
        return usePlugin(MobilePlugin);
    },
});
