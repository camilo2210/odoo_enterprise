import { registry } from "@web/core/registry";
import { openSoftphone } from "./helpers";

registry.category("web_tour.tours").add("call_activity_chatter_link", {
    steps: () => [
        ...openSoftphone(),
        {
            content: "Switch to Activities",
            trigger: ".o-voip-Softphone button[data-tab='activities']",
            run: "click",
        },
        {
            content: "Call Police from the activity",
            trigger: ".o-voip-TabEntry:contains('Police') button[title='Call']",
            run: "click",
        },
        {
            content: "Wait for pick up the call",
            trigger: ".o-voip-InCallView button[title='Transfer']:enabled",
        },
        {
            content: "Hangup the call",
            trigger: ".o-voip-InCallView button[title='Hang up']",
            run: "click",
        },
        {
            content: "Switch to Recent",
            trigger: ".o-voip-Softphone button[data-tab='recent']",
            run: "click",
        },
        {
            content: "Click go to button on Police call",
            trigger: ".o-voip-TabEntry:contains('Police') button[title='Go to']",
            run: "click",
        },
        {
            content: "Open contact form",
            trigger: ".o-dropdown-item span:text('Contact')",
            run: "click",
        },
        {
            content: "Open call record",
            trigger: ".o-mail-Message-textContent a[data-oe-model='voip.call']",
            run: "click",
        },
        {
            content: "Call form opened",
            trigger: ".voip-call-badge span:text('Completed')",
        },
    ],
});
