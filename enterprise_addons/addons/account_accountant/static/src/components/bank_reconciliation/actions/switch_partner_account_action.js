import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export const switchPartnerAccount = {
    dependencies: ["bus_service", "notification", "orm"],
    start(env, { bus_service, notification, orm }) {
        bus_service.subscribe(
            "switch_partner_account_notification",
            ({
                current_partner_name,
                potential_partner_name,
                account_number,
                partner_bank_id,
                potential_partner_id,
            }) => {
                const closeNotification = notification.add(
                    _t(
                        "The bank account %(account_number)s is actually set to partner %(current_partner_name)s, click here to move it to partner %(potential_partner_name)s",
                        { account_number, current_partner_name, potential_partner_name }
                    ),
                    {
                        type: "info",
                        buttons: [
                            {
                                name: _t("Switch"),
                                onClick: async () => {
                                    await orm.write("res.partner.bank", [partner_bank_id], {
                                        partner_id: potential_partner_id,
                                    });
                                    closeNotification();
                                },
                            },
                        ],
                    }
                );
            }
        );
        bus_service.start();
    },
};

registry.category("services").add("switch_partner_account_notification", switchPartnerAccount);
