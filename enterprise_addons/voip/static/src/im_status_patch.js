import { imStatusDataRegistry } from "@mail/core/common/im_status";
import { _t } from "@web/core/l10n/translation";

imStatusDataRegistry.add(
    "voip-phone",
    {
        // VoIP contact suggestions and contact rows pass a partner persona,
        // not always a direct user. Since im_status lives on res.users, inspect
        // the partner users when needed. Keep the phone status hidden when the
        // user is displayed offline so manual offline remains private.
        condition({ persona, user }) {
            const users = user ? [user] : persona?.user_ids ?? [];
            return users.some(
                (candidate) =>
                    candidate.should_display_in_call_im_status && candidate.imStatusUI !== "offline"
            );
        },
        icon: "phone",
        iconClass: "oi-filled",
        title: {
            online: _t("User is on a call and online"),
            away: _t("User is on a call and idle"),
            busy: _t("User is on a call and busy"),
            default: _t("User is on a call"),
        },
    },
    { sequence: 70 }
);
