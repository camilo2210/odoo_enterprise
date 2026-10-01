import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("voip_no_content_softphone_tour", {
    steps: () => [
        {
            content: "Provide a microphone in case the softphone asks for one",
            trigger: "body",
            run() {
                navigator.mediaDevices.getUserMedia = async () => new MediaStream();
            },
        },
        {
            content: "Check that the softphone icon is rendered in the empty list help",
            trigger: ".o_view_nocontent .o-voip-NoContentSoftphone .oi[data-icon='phone']",
        },
        {
            content: "Check that the softphone is not displayed yet",
            trigger: "body:not(:has(.o-voip-Softphone))",
        },
        {
            content: "Open the softphone from the empty list help",
            trigger: ".o_view_nocontent .o-voip-NoContentSoftphone",
            run: "click",
        },
        {
            content: "Check that the softphone is displayed",
            trigger: ".o-voip-Softphone",
        },
    ],
});
