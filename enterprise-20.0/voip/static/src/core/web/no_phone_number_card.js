import { Component, onWillStart, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

/**
 * "No phone number yet" empty-state card, shared by the softphone Recent tab
 * and the backend phone-number-required list views.
 *
 */
export class NoPhoneNumberCard extends Component {
    static template = "voip.NoPhoneNumberCard";

    props = useProps({
        inline: t.boolean().optional(),
        internalCallingAvailable: t.boolean().optional(),
    });

    setup() {
        this.actionService = useService("action");
        onWillStart(async () => {
            this.isUserVoipAdmin = await user.hasGroup("voip.group_voip_admin");
        });
    }

    openPhoneNumberPurchaseWizard() {
        this.actionService.doAction("voip.action_voip_did_number_search_wizard");
    }

    /** @returns {string} */
    get description() {
        if (this.props.internalCallingAvailable) {
            return _t(
                "Internal calls are available through your extension. Get a company number to make and receive external calls."
            );
        }
        if (this.props.internalCallingAvailable === false) {
            return this.isUserVoipAdmin
                ? _t(
                      "Internal calling is not configured for this user. Activate Odoo Phone and configure an extension before calling."
                  )
                : _t(
                      "Internal calling is not configured. Ask your administrator to activate Odoo Phone and configure an extension."
                  );
        }
        return this.isUserVoipAdmin
            ? _t("Purchase a phone number to make and receive calls with Odoo Phone Service.")
            : _t(
                  "Ask your administrator to purchase a phone number for calls through Odoo Phone Service."
              );
    }

    /** @returns {string} */
    get title() {
        return this.props.internalCallingAvailable === undefined
            ? _t("No Phone numbers yet")
            : _t("No active phone number");
    }
}
