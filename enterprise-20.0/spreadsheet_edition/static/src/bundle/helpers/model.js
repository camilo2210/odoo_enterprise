// @ts-check

import { helpers } from "@odoo/o-spreadsheet";
import { OdooSpreadsheetModel } from "@spreadsheet/model";

import { OdooDataProvider } from "@spreadsheet/data_sources/odoo_data_provider";

const { UuidGenerator } = helpers;

import { browser } from "@web/core/browser/browser";
import { createDefaultCurrency } from "@spreadsheet/currency/helpers";
import { user } from "@web/core/user";
import { randomAnonymousName } from "./random_anonymous_name";

export async function createSpreadsheetCollaborativeModel({
    url,
    resModel,
    resId,
    shareId,
    accessToken,
    mode,
    env,
}) {
    const response = await browser.fetch(url, {
        method: "GET",
    });
    if ([403, 404].includes(response.status)) {
        return;
    }
    const data = await response.json();
    const spreadsheetService = env.services.spreadsheet_collaborative;
    const transportService =
        mode === "normal"
            ? spreadsheetService.makeCollaborativeChannel(resModel, resId, shareId, accessToken)
            : undefined;
    const odooDataProvider = new OdooDataProvider(env);
    odooDataProvider.addEventListener("data-source-updated", () => {
        model.dispatch("EVALUATE_CELLS");
    });
    const config = {
        custom: {
            env,
            orm: env.services.orm,
            odooDataProvider,
            isFrozenSpreadsheet: env.isFrozenSpreadsheet?.(),
        },
        external: {
            geoJsonService: env.services.geo_json_service,
        },
        defaultCurrency: createDefaultCurrency(data.default_currency),
        transportService,
        client: {
            id: UuidGenerator.smallUuid(),
            name: user.userId !== null ? user.name : randomAnonymousName(),
            userId: user.userId,
        },
        mode,
        snapshotRequested: data.snapshot_requested,
        customColors: data.company_colors,
    };
    const model = new OdooSpreadsheetModel(data.data, config, data.revisions);
    return model;
}
