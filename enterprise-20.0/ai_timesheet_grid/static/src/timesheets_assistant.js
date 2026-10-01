import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { useDebounced } from "@web/core/utils/timing";
import { TimesheetsAssistant } from "@timesheet_grid/components/aw_timesheet/aw_timesheet";

patch(TimesheetsAssistant.prototype, {
    setup() {
        super.setup();
        this.debouncedUpdateDescription = useDebounced(
            this._updateDescriptionWithAI.bind(this),
            800
        );
    },

    async _updateDescriptionWithAI(name) {
        let description = name;
        try {
            const summary = await rpc("/ai/get_direct_response", {
                interface_key: "timesheet_assistant_ai",
                prompt:
                    "Summarize the following timesheet activities into one short description. " +
                    "Return only the summary.\n\n" +
                    name,
            });
            description = summary?.trim() || name;
            this.currentRecord.update({ name: description });
        } catch {}
    },

    /** @override */
    async updateRecordInForm() {
        await super.updateRecordInForm();
        if (!this.model.isAgentAvailable || this.state.selectedRows.size < 2 || !this.currentRecord) {
            return;
        }
        this.debouncedUpdateDescription(this.selectedData.name);
    },
});
