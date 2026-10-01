import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const voipErrorService = {
    dependencies: ["bus_service", "notification"],
    start(_, { notification, bus_service }) {
        bus_service.subscribe("voip.call/event_not_processed", ({ id, from }) => {
            notification.add(
                _t("Unable to process voip webhook event: %(id)s (from caller %(from)s)", {
                    id,
                    from,
                }),
                {
                    type: "warning",
                }
            );
        });
    },
};

registry.category("services").add("voip_error", voipErrorService);
