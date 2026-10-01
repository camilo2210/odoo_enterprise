/* eslint-env serviceworker */
/* eslint-disable no-restricted-globals */
/* eslint-disable no-undef */

const callStateByTag = new Map();
const pendingNotificationActionsByResId = new Map();
const clickedNotificationsByTag = new Map();
const notificationBroadcastChannel = new BroadcastChannel("voip_notification_channel");
const DELAY = 1_000 * 60 * 60 * 4; // 4 hours
const NOTIFICATION_ACTION_DELAY = 1_000 * 60;
const USER_AGENT_READY_TIMEOUT = 1_000 * 10;
function freeExpiredRefs() {
    const now = Date.now();
    for (const map of [
        callStateByTag,
        pendingNotificationActionsByResId,
        clickedNotificationsByTag,
    ]) {
        for (const [key, { expires }] of map) {
            if (expires <= now) {
                map.delete(key);
            }
        }
    }
}
setInterval(() => freeExpiredRefs(), DELAY);

function buildNotificationActionData(data, action) {
    return {
        ...data,
        type: "VOIP:CALL_NOTIFICATION_CLICK",
        action,
    };
}

async function declineIncomingCallServerSide(resId) {
    if (!resId) {
        return;
    }
    try {
        await fetch("/voip/decline_incoming_call", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: { call_id: resId },
            }),
        });
    } catch {
        // Best effort: on failure the PBX rings out to its own timeout.
    }
}

function storePendingNotificationAction(data, action) {
    if (!data.res_id) {
        return;
    }
    // When a notification opens Odoo, the page can need several seconds to
    // load assets and register SIP. Keep the click action in the service
    // worker so the new user agent can pull it once it is actually listening.
    pendingNotificationActionsByResId.set(data.res_id, {
        expires: Date.now() + NOTIFICATION_ACTION_DELAY,
        actionData: buildNotificationActionData(data, action),
    });
}

function broadcastPendingNotificationActions() {
    freeExpiredRefs();
    for (const [resId, { actionData }] of pendingNotificationActionsByResId) {
        notificationBroadcastChannel.postMessage(actionData);
        pendingNotificationActionsByResId.delete(resId);
    }
}

notificationBroadcastChannel.addEventListener("message", ({ data }) => {
    if (data?.type === "VOIP:GET_PENDING_NOTIFICATION_ACTIONS") {
        broadcastPendingNotificationActions();
    }
});

// Push-arrival counterpart of CALL_STATE_TRANSITIONS["incoming"] from
// models/voip_call.py. Pushes are only sent after a committed server
// transition, but web push can drop or reorder deliveries, so a pair is
// valid here when some chain of server transitions links its two states —
// even if the direct pair is no server transition. States the webhook
// pipeline never pushes (ended_unexpectedly) are omitted.
const INCOMING_CALL_STATE_TRANSITIONS = [
    // Valid transitions
    ["calling", "ongoing"],
    ["ongoing", "terminated"],
    ["calling", "rejected"],
    ["calling", "missed"],
    ["calling", "completed_elsewhere"],

    // Allow recovery from tab concurrency issues
    ["rejected", "ongoing"],
    ["missed", "ongoing"],
    ["missed", "rejected"],
    ["completed_elsewhere", "ongoing"],

    // A peer's answer revises a "missed" its own cancel raced into: the
    // notification must drop back from "Missed call" to nothing.
    ["missed", "completed_elsewhere"],

    // Allow out-of-order webhook delivery (hangup processed before answered)
    ["calling", "terminated"],

    // Accept a terminal push whose intermediate "ongoing" push was lost
    // (missed/completed_elsewhere -> ongoing -> terminated on the server)
    ["missed", "terminated"],
    ["completed_elsewhere", "terminated"],
];

const originalHandlePushEvent = handlePushEvent;
handlePushEvent = async function (notification) {
    if (notification.options?.data?.type !== "VOIP:CALL_NOTIFICATION") {
        return originalHandlePushEvent.call(this, notification);
    }
    const { data } = notification.options;
    const tag = `voip.call_${data.res_id}`;
    if (callStateByTag.has(tag)) {
        const { callState } = callStateByTag.get(tag);
        const isValidTransition = INCOMING_CALL_STATE_TRANSITIONS.some(
            ([cur, next]) => cur === callState && next === data.call_state
        );
        // A same-state push (e.g. another leg of a queue conversation) is not a
        // transition: the shown notification already carries the control handle
        // every leg shares, so its Answer/Decline targets the new INVITE too.
        if (!isValidTransition) {
            return;
        }
    }
    callStateByTag.set(tag, {
        expires: Date.now() + DELAY,
        callState: data.call_state,
    });
    const notifications = await self.registration.getNotifications({ tag });
    for (const notif of notifications) {
        notif.close();
    }
    // Clicking the notification — answer or plain activation — registers the
    // softphone, which the PBX then dials back through a new leg: that push
    // keeps the call in "calling" with a new SIP Call-ID, and must not
    // re-ring a call the user already acted on.
    if (data.call_state === "calling" && clickedNotificationsByTag.has(tag)) {
        return;
    }
    if (["calling", "missed"].includes(data.call_state)) {
        return self.registration.showNotification(notification.title, {
            ...notification.options,
            tag,
        });
    }
};

const originalHandleNotificationClick = handleNotificationClick;
handleNotificationClick = async function (ev) {
    const { data } = ev.notification;
    if (data.type !== "VOIP:CALL_NOTIFICATION") {
        return originalHandleNotificationClick.call(this, ev);
    }
    clickedNotificationsByTag.set(ev.notification.tag, {
        expires: Date.now() + NOTIFICATION_ACTION_DELAY,
    });
    if (ev.action === "VOIP:DECLINE_INCOMING_CALL") {
        const windowClients = await self.clients.matchAll({
            includeUncontrolled: true,
            type: "window",
        });
        const hasOdooTab = windowClients.some((c) => new URL(c.url).pathname.startsWith("/odoo"));
        if (hasOdooTab) {
            // A tab is open: let it reject the local SIP INVITE. Broadcast
            // rather than postMessage a matched client because we can't tell
            // which open tab owns the INVITE; the tab holding the matching
            // Odoo call id / SIP Call-ID self-selects and the rest ignore it.
            notificationBroadcastChannel.postMessage(buildNotificationActionData(data, ev.action));
        } else {
            // No tab to reject the INVITE: decline server-side via the PBX.
            await declineIncomingCallServerSide(data.res_id);
        }
        return;
    }
    let client;
    const clients = await self.clients.matchAll({
        includeUncontrolled: true,
        type: "window",
    });
    const openedNewClient = clients.length === 0;
    if (openedNewClient) {
        const url = new URL("/odoo", location.origin);
        client = await self.clients.openWindow(url.toString());
        storePendingNotificationAction(data, ev.action);
    } else {
        client =
            clients.find(
                (c) =>
                    c.visibilityState === "visible" && new URL(c.url).pathname.startsWith("/odoo")
            ) ||
            clients.find((c) => new URL(c.url).pathname.startsWith("/odoo")) ||
            clients.find((c) => c.visibilityState === "visible") ||
            clients[0];
        try {
            await client.focus();
        } catch {
            // ignore
        }
    }
    if (data.control_handle && !openedNewClient) {
        // Wazo already sent the INVITE to registered browser SIP endpoints.
        // Broadcast rather than postMessage a matched client because we can't
        // tell which open tab owns the INVITE; the tab whose session shares the
        // control handle self-selects and answers, the rest ignore it.
        notificationBroadcastChannel.postMessage(
            buildNotificationActionData(ev.notification.data, ev.action)
        );
        return;
    }
    // Start waiting before asking, so a client answering right away is not missed.
    // The signal matters as much as the timeout: it drops the resolver the service
    // worker holds for that client, which would otherwise be kept forever.
    const clientReadyProm = waitingMessage("VOIP:USER_AGENT_IS_LISTENING", client.id, {
        signal: AbortSignal.timeout(USER_AGENT_READY_TIMEOUT),
    });
    client.postMessage({ type: "VOIP:IS_USER_AGENT_LISTENING?" });
    try {
        await clientReadyProm;
    } catch {
        // The client never confirmed its user agent is listening: keep the action
        // pending so that it is replayed once a listening client shows up.
        storePendingNotificationAction(data, ev.action);
        return;
    }
    const actionData = buildNotificationActionData(ev.notification.data, ev.action);
    pendingNotificationActionsByResId.delete(data.res_id);
    client.postMessage(actionData);
};
