import { useBus } from "@web/core/utils/hooks";
import { aiChannelBus } from "./ai_channel_bus";

export const triggers = new Set(["view", "mediaDialog"]);

export async function getData(data_source) {
    if (!triggers.has(data_source)) {
        throw new Error(`Invalid data source ${data_source}`);
    }
    const requestTrigger = getRequestTrigger(data_source);
    const sendTrigger = getSendTrigger(data_source);
    return new Promise((resolve) => {
        const listener = ({ detail }) => {
            aiChannelBus.removeEventListener(sendTrigger, listener);
            clearTimeout(timeout);
            resolve(detail);
        };
        const timeout = setTimeout(() => {
            aiChannelBus.removeEventListener(sendTrigger, listener);
            resolve(null);
        }, 100);
        aiChannelBus.addEventListener(sendTrigger, listener);
        aiChannelBus.trigger(requestTrigger);
    });
}

export function useDataGetter(data_source, getter) {
    if (!triggers.has(data_source)) {
        throw new Error(`Invalid data source ${data_source}`);
    }
    const requestTrigger = getRequestTrigger(data_source);
    const sendTrigger = getSendTrigger(data_source);
    useBus(aiChannelBus, requestTrigger, async () => {
        aiChannelBus.trigger(sendTrigger, await getter());
    });
}

function getRequestTrigger(data_source) {
    return `${data_source}?`;
}

function getSendTrigger(data_source) {
    return `${data_source}!`;
}
