import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

// todo: make it a function? why is this a service
export const aiChatLauncherService = {
    dependencies: ["mail.store", "orm", "action"],
    start(env, services) {
        const actionService = services["action"];
        const mailStore = services["mail.store"];

        async function openFullComposer(msgType, resModel, resId, message) {
            let allRecipients = [];
            const thread = await mailStore["mail.thread"].getOrFetch({
                model: resModel,
                id: resId,
            });
            if (msgType === "message") {
                allRecipients = [...thread.suggestedRecipients, ...thread.additionalRecipients];
                // auto-create partner
                const newPartners = allRecipients.filter((recipient) => !recipient.partner_id);
                if (newPartners.length !== 0) {
                    const recipientEmails = [];
                    newPartners.forEach((recipient) => {
                        recipientEmails.push(recipient.email);
                    });
                    const partners = await rpc("/mail/partner/from_email", {
                        thread_model: thread.model,
                        thread_id: thread.id,
                        emails: recipientEmails,
                    });
                    for (const index in partners) {
                        const partnerData = partners[index];
                        const partner = mailStore["res.partner"].insert(partnerData);
                        const email = recipientEmails[index];
                        const recipient = allRecipients.find(
                            (recipient) => recipient.email === email
                        );
                        recipient.partner_id = partner.id;
                    }
                }
            }
            actionService.doAction(
                {
                    name: msgType === "message" ? _t("Send Message") : _t("Log Note"),
                    res_model: "mail.compose.message",
                    target: "new",
                    type: "ir.actions.act_window",
                    view_id: false,
                    view_mode: "form",
                    views: [[false, "form"]],
                    context: {
                        is_full_composer: true,
                        default_body: message.body,
                        default_model: resModel,
                        default_partner_ids: allRecipients
                            .filter((r) => r.recipient_type !== "cc")
                            .map((r) => r.partner_id),
                        default_partner_cc_ids: allRecipients
                            .filter((r) => r.recipient_type === "cc")
                            .map((r) => r.partner_id),
                        default_res_ids: [resId],
                        default_subtype_xmlid:
                            msgType === "message" ? "mail.mt_comment" : "mail.mt_note",
                        default_attachment_ids: message.attachment_ids.map(
                            (attachment) => attachment.id
                        ),
                    },
                },
                { onClose: () => thread?.fetchNewMessages() }
            );
        }

        function getLastAiChat({ interfaceKey, recordModel, recordId }) {
            if (!["chatter_ai_button", "systray_ai_button"].includes(interfaceKey)) {
                return;
            }
            return mailStore.messagingMenu.aiChatTab.channels.find(
                (channel) =>
                    channel.isLoaded &&
                    channel.ai_session_ids.some(
                        (session) =>
                            session.ai_composer_id?.interface_key === interfaceKey &&
                            (session.res_model === recordModel ||
                                (!session.res_model && !recordModel)) &&
                            (session.res_id === recordId || (!session.res_id && !recordId))
                    )
            );
        }

        return {
            async launchAIChat({
                interfaceKey,
                channelTitle,
                recordModel = null,
                recordId = null,
                aiSpecialActions = null,
                aiChatSourceId = null,
                textSelection = null,
                textOfEditable = null,
                userMessage = null,
                referenceImagePath = null,
                context = null,
            }) {
                // make the insert button target the component that called the AI
                if (aiChatSourceId) {
                    services["mail.store"].aiInsertButtonTarget = aiChatSourceId;
                }
                // when creating an AI chat and when the last chat with the same configuration is
                // empty, return that chat instead (to avoid creating several empty chats when
                // clicking several times on the "create AI chat" button)
                const lastAiChat = getLastAiChat({ interfaceKey, recordModel, recordId });
                if (lastAiChat?.isEmpty) {
                    if (services["mail.store"].discuss.isActive) {
                        lastAiChat.setAsDiscussThread();
                    } else {
                        await lastAiChat.openChatWindow({ focus: true });
                    }
                    if (userMessage) {
                        lastAiChat.post(userMessage);
                    }
                    return lastAiChat;
                }

                const { ai_channel_id, data, model_has_thread } = await services.orm.call(
                    "ai.agent",
                    "action_launch_ai_chat",
                    [
                        interfaceKey,
                        recordModel,
                        recordId,
                        channelTitle,
                        textSelection?.textContent,
                        textOfEditable,
                        referenceImagePath,
                    ],
                    { context }
                );
                services["mail.store"].insert(data);
                const channel = await services["mail.store"]["discuss.channel"].getOrFetch(
                    ai_channel_id
                );
                // add sendMessage and logNote only if the model inherits from mail.thread
                if (interfaceKey === "chatter_ai_button" && model_has_thread) {
                    aiSpecialActions = {
                        ...(aiSpecialActions || {}),
                        sendMessage: (message) =>
                            openFullComposer("message", recordModel, recordId, message),
                        logNote: (message) =>
                            openFullComposer("note", recordModel, recordId, message),
                    };
                }
                channel.aiSpecialActions = aiSpecialActions;
                channel.textSelection = textSelection;
                channel.aiChatSource = aiChatSourceId;
                channel.open({ focus: true });
                channel.openChatWindow();
                if (userMessage) {
                    channel.post(userMessage);
                }
                return channel;
            },
        };
    },
};

registry.category("services").add("aiChatLauncher", aiChatLauncherService);
