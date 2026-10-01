import { registry } from "@web/core/registry";
import { openSoftphone } from "./helpers";

registry.category("web_tour.tours").add("voip_log_after_call_tour", {
    steps: () => [
        ...openSoftphone(),
        {
            content: "Switch to Recent",
            trigger: ".o-voip-Softphone button[data-tab='recent']",
            run: "click",
        },
        {
            content: "Switched to Recent",
            trigger: "button[data-tab='recent'].active",
        },
        {
            content: "Search for Police",
            trigger: "input[id='o-voip-Tab-searchInput']",
            run: "edit Police",
        },
        {
            content: "Call Police",
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
            content: "Click Log",
            trigger: ".o-voip-TabEntry:contains('Police') button[title='Log']",
            run: "click",
        },
        {
            content: "Click Mark Done",
            trigger: "button[name='action_schedule_activities_done']",
            run: "click",
        },
        {
            content: "Check no Log button",
            trigger: ".o-voip-TabEntry:contains('Police'):not(:has(button[title='Log']))",
        },
        {
            content: "Click go to",
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

registry.category("web_tour.tours").add("voip_log_during_call_tour", {
    steps: () => [
        ...openSoftphone(),
        {
            content: "Switch to Recent",
            trigger: ".o-voip-Softphone button[data-tab='recent']",
            run: "click",
        },
        {
            content: "Switched to Recent",
            trigger: "button[data-tab='recent'].active",
        },
        {
            content: "Search for Ambulance",
            trigger: "input[id='o-voip-Tab-searchInput']",
            run: "edit Ambulance",
        },
        {
            content: "Call Ambulance",
            trigger: ".o-voip-TabEntry:contains('Ambulance') button[title='Call']",
            run: "click",
        },
        {
            content: "Click Log",
            trigger: ".o-voip-InCallView:contains('Ambulance') button[title='Log']",
            run: "click",
        },
        {
            content: "Click Mark Done",
            trigger: "button[name='action_schedule_activities']",
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
            content: "Check no Log button",
            trigger: ".o-voip-TabEntry:contains('Ambulance'):not(:has(button[title='Log']))",
        },
        {
            content: "Click go to",
            trigger: ".o-voip-TabEntry:contains('Ambulance') button[title='Go to']",
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
