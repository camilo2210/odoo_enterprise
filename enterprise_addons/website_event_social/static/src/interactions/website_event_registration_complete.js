import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { _t } from "@web/core/l10n/translation";

export class WebsiteEventRegistrationComplete extends Interaction {
    static selector = ".o_wereg_js_confirmed";
    start() {
        this.env.bus.trigger("SOCIAL_PUSH_NOTIFICATIONS:SHOW_PUSH_NOTIFICATION_REQUEST", {
            icon: "/mail/static/src/img/odoobot_transparent.webp",
            title: _t("Allow push notifications?"),
            body: _t("You have to enable push notifications to get reminders for your favorite tracks."),
        });
    }
}

registry.category("public.interactions").add(
    "website_event_social.website_event_registration_complete",
    WebsiteEventRegistrationComplete
);
