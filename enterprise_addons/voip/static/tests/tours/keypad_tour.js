import { registry } from "@web/core/registry";
import { openSoftphone } from "./helpers";

let blurFailHandler;

registry.category("web_tour.tours").add("keypad_tour", {
    steps: () => [
        ...openSoftphone(),
        {
            content: "Switch to Keypad",
            trigger: ".o-voip-Softphone button[data-tab='dialer']",
            run: "click",
        },
        {
            content: "Make sure the keypad is opened",
            trigger: ".o-voip-Softphone button[data-tab='dialer'].active",
        },
        {
            content: "Make sure the input is focused",
            trigger: ".o-voip-Keypad-searchBar input",
            run: function () {
                // It should already be the case but for some reason it is not
                // reliable in this tour.
                this.anchor.focus();

                // Add a blur event listener to fail the test if the input loses
                // focus with the next actions (clicking the keypad buttons).
                // Remove it at the end, otherwise destroying the test might
                // call the handler by mistake.
                // Note that this was tested as a tour instead of a unit test
                // because simulating "real blur" that occurs upon click did not
                // seem to be working using standard utils in unit tests.
                blurFailHandler = () => {
                    throw new Error("Input should not lose focus");
                };
                this.anchor.addEventListener("blur", blurFailHandler);
            },
        },
        {
            content: "Click on keypad button '8'",
            trigger: ".o-voip-Keypad-digitBtn:has(> span:text('8'))",
            run: "click",
        },
        {
            content: "Check that the input contains '8'",
            trigger: ".o-voip-Keypad-searchBar input:value('8')",
            run: function () {
                this.anchor.removeEventListener("blur", blurFailHandler);
            },
        },
    ],
});
