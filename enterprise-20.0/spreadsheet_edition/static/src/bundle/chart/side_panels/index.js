import * as spreadsheet from "@odoo/o-spreadsheet";
import { OdooChartDataSourceConfigPanel } from "./common/config_panel";

const { chartDataSourceSidePanelComponentRegistry } = spreadsheet.registries;

chartDataSourceSidePanelComponentRegistry.add("odoo", OdooChartDataSourceConfigPanel);
