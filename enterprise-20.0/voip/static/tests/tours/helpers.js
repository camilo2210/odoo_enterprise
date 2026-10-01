export function openSoftphone() {
    return [
        {
            content: "Provide a microphone for demo calls",
            trigger: "body",
            run() {
                navigator.mediaDevices.getUserMedia = async () => new MediaStream();
            },
        },
        {
            content: "Open softphone",
            trigger: "[data-icon='phone']",
            run: "click",
        },
        {
            content: "Wait until sip.js has loaded and registration is complete",
            trigger: ".o-voip-Softphone:not(:has(.o-voip-ErrorScreen))",
        },
    ];
}
