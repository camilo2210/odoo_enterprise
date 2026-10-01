import { click, contains, insertText, mailModels } from "@mail/../tests/mail_test_helpers";
import { afterEach } from "@odoo/hoot";
import { mockWorker } from "@odoo/hoot-mock";
import { MailActivity } from "@voip/../tests/mock_server/mock_models/mail_activity";
import { ResPartner } from "@voip/../tests/mock_server/mock_models/res_partner";
import { ResUsers } from "@voip/../tests/mock_server/mock_models/res_users";
import { ResUsersSettings } from "@voip/../tests/mock_server/mock_models/res_users_settings";
import { VoipCall } from "@voip/../tests/mock_server/mock_models/voip_call";
import { VoipCallLeg } from "@voip/../tests/mock_server/mock_models/voip_call_leg";
import { VoipConversation } from "@voip/../tests/mock_server/mock_models/voip_conversation";
import { VoipProvider } from "@voip/../tests/mock_server/mock_models/voip_provider";
import { VoipQueueAgent } from "@voip/../tests/mock_server/mock_models/voip_queue_agent";
import { Ringtone } from "@voip/core/web/ringtone";
import { Voip } from "@voip/core/web/voip_service";
import { VoipWorker } from "@voip/worker/voip_worker";
import {
    defineModels,
    getService,
    MockServer,
    onRpc,
    patchWithCleanup,
    preloadBundle,
} from "@web/../tests/web_test_helpers";

/**
 * @param {{
 *  sip_call_id: string;
 *  headers: string;
 *  phone_number: string;
 *  onAccept: () => any;
 *  onProgress: () => any;
 *  onReject: () => any;
 * }} options
 * @returns
 */
export function receiveInvite(options = {}, env) {
    const inviteSession = new SIP.Invitation();
    inviteSession._configureWith({
        sip_call_id: options.sip_call_id,
        headers: options.headers,
        phone_number: options.phone_number,
    });
    if (options.onAccept) {
        inviteSession._onAccept = options.onAccept;
    }
    if (options.onProgress) {
        inviteSession._onProgress = options.onProgress;
    }
    if (options.onReject) {
        inviteSession._onReject = options.onReject;
    }
    const voipService = env ? env.services["voip"] : getService("voip");
    voipService.userAgent._onIncomingInvitation(inviteSession);
    return inviteSession;
}

let voipWorker = null;

export function setupVoipTests({ extraModels } = {}) {
    onRpc("/voip/parse_phone_number", async (args) => {
        const { params } = await args.json();
        return {
            countryId: 1,
            isValid: false,
            phone_number: params.data.phone_number,
            storeData: {
                "res.country": {
                    id: 1,
                    name: "Belgium",
                    code: "BE",
                    phone_code: "32",
                    image_url: "/base/static/img/flags/be.png",
                },
            },
        };
    });
    preloadBundle("voip.assets_sip_tests");
    patchWithCleanup(navigator.mediaDevices, {
        async getUserMedia() {
            const audioTrack = {
                enabled: true,
                kind: "audio",
                readyState: "live",
                stop() {
                    this.readyState = "ended";
                },
            };
            return {
                getAudioTracks: () => [audioTrack],
                getTracks: () => [audioTrack],
            };
        },
    });
    patchWithCleanup(Ringtone.prototype, { play() {}, stop() {} });
    patchWithCleanup(Voip.prototype, {
        get sipBundle() {
            return "voip.assets_sip_tests";
        },
    });
    afterEach(() => {
        voipWorker = null;
        SIP?.UserAgent?._instances?.clear();
    });
    patchWithCleanup(MockServer.prototype, {
        start() {
            if (voipWorker) {
                return;
            }
            voipWorker = new VoipWorker();
            mockWorker(function onWorkerConnected(worker) {
                const client = worker._messageChannel.port2;
                client.addEventListener("message", voipWorker.handleMessage.bind(voipWorker));
                client.start();
            });

            return super.start(...arguments);
        },
    });
    defineModels({ ...voipModels, ...extraModels });
}

export const voipModels = {
    ...mailModels,
    MailActivity,
    ResPartner,
    ResUsers,
    ResUsersSettings,
    VoipCall,
    VoipCallLeg,
    VoipConversation,
    VoipProvider,
    VoipQueueAgent,
};

export async function openSoftphone({ selector = "", waitNoErrorDisplayed = true } = {}) {
    const prefix = selector ? `${selector} ` : "";
    await click(`${prefix}.o_menu_systray button[title='Show Softphone']`);
    if (waitNoErrorDisplayed) {
        await contains(`${prefix}.o-voip-Softphone:not(:has(.o-voip-ErrorScreen))`);
    } else {
        await contains(`${prefix}.o-voip-Softphone`);
    }
}

export async function openRecentContactSearch(searchTerm) {
    await openSoftphone();
    await click("button[data-tab='recent']");
    await insertText("input[id='o-voip-Tab-searchInput']", searchTerm);
    await contains("button[data-tab='recent'].active");
    await contains(".o-voip-AddressBook");
}
