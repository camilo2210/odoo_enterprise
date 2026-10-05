import { Component, onMounted, signal, t, usePlugin, useProps } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";


export class AccountReportSearchBar extends Component {
    static template = "account_reports.AccountReportSearchBar";
    props = useProps({
        initialQuery: t.string().optional(),
    });

    controller = usePlugin(AccountReportController);

    searchBarInputRef = signal.ref();

    setup() {
        onMounted(() => {
            if (!this.props.initialQuery) return;
            this.searchBarInputRef().value = this.props.initialQuery || "";
            this.search();
        });
    }

    //------------------------------------------------------------------------------------------------------------------
    // Search
    //------------------------------------------------------------------------------------------------------------------
    async search() {
        const inputText = this.searchBarInputRef().value.trim();
        const query = inputText.toLowerCase();

        // Since the search bar is loaded before the report data, we need to wait for it
        await this.controller.reportLoadingPromise;

        if (query.length) {
            const parentLines = [];
            let parentLineId = undefined;
            for (const line of this.controller.lines) {
                while (parentLines.length && parentLines.at(-1).level >= line.level) {
                    parentLines.pop();
                }

                if (parentLineId && !line.id.startsWith(`${parentLineId}|`)) {
                    parentLineId = undefined;
                }

                line.search_match = false;
                if (line.name) {
                    const lineName = line.name.trim().toLowerCase();
                    const match = (lineName.indexOf(query) !== -1);

                    if (match) {
                        line.search_match = true;
                        // update parent lines to be visible if a child line matches the search
                        for (let i = parentLines.length - 1; i >= 0; i--) {
                            parentLines[i].search_match = true;
                        }
                        if (!parentLineId || !line.id.startsWith(`${parentLineId}|`)) {
                            parentLineId = line.id;
                        }
                    }
                }

                if (parentLineId && line.id.startsWith(`${parentLineId}|`)) {
                    line.search_match = true;
                }

                parentLines.push(line);
            }
            this.controller.updateOption("filter_search_bar", inputText);
        } else {
            for (const line of this.controller.lines) {
                line.search_match = true;
            }
            this.controller.deleteOption("filter_search_bar");
        }
        this.controller.invalidateVisibleLines();  // This update search_match on the stored lines.
    }
}
