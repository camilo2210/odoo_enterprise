import { render } from "@web/owl2/utils";
import { EnterpriseNavBar } from "@web_enterprise/webclient/navbar/navbar";
import { SpreadsheetSyncStatus } from "../spreadsheet_sync_status/spreadsheet_sync_status";
import { SpreadsheetName } from "../../actions/control_panel/spreadsheet_name";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount, proxy, t, useProps } from "@odoo/owl";

export class SpreadsheetNavbar extends EnterpriseNavBar {
    static template = "spreadsheet_edition.SpreadsheetNavbar";
    static components = { ...EnterpriseNavBar.components, SpreadsheetName, SpreadsheetSyncStatus };

    props = useProps({
        spreadsheetName: t.string(),
        isReadonly: t.boolean().optional(),
        onSpreadsheetNameChanged: t.function().optional(),
        model: t.object().optional(),
    });

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.breadcrumbs = proxy(this.env.config.breadcrumbs);

        if (this.props.model) {
            onMounted(() => {
                this.props.model.on("update", this, () => render(this, true));
            });
            onWillUnmount(() => {
                this.props.model.off("update", this);
            });
        }
    }

    get breadcrumbTitle() {
        if (this.breadcrumbs.length > 1) {
            return this.breadcrumbs.at(-2).name;
        }
        return "";
    }

    onBreadcrumbClicked() {
        if (this.breadcrumbs.length > 1) {
            this.actionService.restore(this.breadcrumbs.at(-2).id);
        }
    }
}
