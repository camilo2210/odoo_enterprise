import { registry } from "@web/core/registry";
import { openSoftphone } from "./helpers";

registry.category("web_tour.tours").add("country_selector_tour", {
    steps: () => [
        ...openSoftphone(),
        {
            content: "Switch to Keypad",
            trigger: ".o-voip-Softphone button[data-tab='dialer']",
            run: "click",
        },
        {
            content: "Open country selector",
            trigger: ".o-voip-Keypad-searchBar .o-voip-countryFlag",
            run: "click",
        },
        {
            content: "Check that the country filter input is focused",
            trigger: ".o-voip-countryDropdown-search input:focus",
        },
        {
            content: "Type 'be' to filter countries",
            trigger: ".o-voip-countryDropdown-search input",
            run: "edit be",
        },
        {
            content: "Select Belgium",
            trigger: '.o-dropdown-item span:contains("Belgium")',
            run: "click",
        },
        {
            content: "Check that the country flag has been updated",
            trigger:
                ".o-voip-Softphone img.o-voip-countryFlag[src='/base/static/img/country_flags/be.png']",
        },
        {
            content:
                "Check country code is already in the input, and type a valid number in local format",
            trigger: ".o-voip-Softphone input.o-voip-Keypad-input[data-value='+32']",
            run: "edit 0474123456",
        },
        {
            content: "Phone number is formatted correctly",
            trigger: ".o-voip-Softphone input.o-voip-Keypad-input[data-value='+32 474 12 34 56']",
        },
        {
            content: "Open country selector again",
            trigger: ".o-voip-Softphone .o-voip-countryFlag",
            run: "click",
        },
        {
            content: "Type 'fr' to filter countries",
            trigger: ".o-voip-countryDropdown-search input",
            run: "edit fr",
        },
        {
            content: "Select France",
            trigger: '.o-dropdown-item span:contains("France")',
            run: "click",
        },
        {
            content: "Check that the country flag has been updated",
            trigger:
                ".o-voip-Softphone img.o-voip-countryFlag[src='/base/static/img/country_flags/fr.png']",
        },
        {
            content: "Check phone number has been reformatted for France",
            trigger: ".o-voip-Softphone input.o-voip-Keypad-input[data-value='+33 4 74 12 34 56']",
        },
        {
            content: "Delete one digit to make the number invalid",
            trigger: ".o-voip-Keypad-searchBar i[data-icon='backspace']",
            run: "click",
        },
        {
            content: "Check phone number is now unformatted",
            trigger: ".o-voip-Softphone input.o-voip-Keypad-input[data-value='+3347412345']",
        },
    ],
});
