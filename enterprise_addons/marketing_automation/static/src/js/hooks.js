import { _t } from "@web/core/l10n/translation";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";

/** @returns {Function} */
export function useSendToMarketingCampaign() {
    const openDialog = useOwnedDialogs();
    const orm = useService("orm");
    const notification = useService("notification");
    /**
     * @param {String} resModel
     * @param {Array[integer]} resIds
     * @param {Function} onCloseCallback
     */
    return (resModel, resIds, onCloseCallback = () => {}) =>
        openDialog(
            SelectCreateDialog,
            {
                title: _t("Select a campaign"),
                noCreate: true,
                multiSelect: false,
                resModel: "marketing.campaign",
                domain: [["model_name", "=", resModel]],
                dynamicFilters: [
                    {
                        description: _t("Running Campaigns"),
                        domain: [["state", "=", "running"]],
                    },
                ],
                /** @param {Array[integer]} campaignIds */
                onSelected: async (campaignIds) => {
                    const participants = await orm.call(
                        "marketing.campaign",
                        "action_add_participants_manually",
                        [campaignIds[0]],
                        {
                            model_name: resModel,
                            record_ids: resIds,
                        }
                    );
                    if (participants.length > 0) {
                        notification.add(_t("Records added to the campaign!"), {
                            type: "success",
                        });
                    }
                },
            },
            {
                onClose: () => onCloseCallback(),
            }
        );
}
