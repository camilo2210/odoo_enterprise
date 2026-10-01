import { registerMessageAction } from "@mail/core/common/message_actions";
import { AIMessageActions } from "@ai/discuss/message_actions_patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { isAiWebsiteBuilderChannel, isEditorSidebarOpen, isPageAiEditable } from "../utils";

function openWebsiteBuilder({ owner }) {
    const website = owner.websiteService;
    website.goToWebsite({
        path: isPageAiEditable(website) ? website.currentLocation : "/",
        lang: website.currentWebsite?.default_lang_id.code,
        edition: true,
    });
}

AIMessageActions.push("open-website-builder");
registerMessageAction("open-website-builder", {
    setup({ owner }) {
        owner.websiteService = useService("website");
    },
    condition: ({ owner, channel, message }) =>
        isAiWebsiteBuilderChannel(channel) &&
        !isEditorSidebarOpen(owner.websiteService) &&
        !message.isSelfAuthored &&
        message.eq(channel?.newestMessage),
    name: _t("Open Website Builder"),
    onSelected: openWebsiteBuilder,
    sequence: 5,
});
