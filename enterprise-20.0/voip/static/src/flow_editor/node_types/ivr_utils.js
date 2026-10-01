import { _t } from "@web/core/l10n/translation";

/**
 * Load an IVR and build stable output ports from its options.
 *
 * @param {Object} orm
 * @param {number} ivrId
 */
export async function loadIvrNodeData(orm, ivrId) {
    const [ivr] = await orm.read("voip.ivr", [ivrId], ["display_name", "option_ids"]);
    const optionRecords = ivr.option_ids.length
        ? await orm.read("voip.ivr.option", ivr.option_ids, ["digit"])
        : [];
    const optionsById = Object.fromEntries(optionRecords.map((option) => [option.id, option]));
    const outputs = [
        ...ivr.option_ids.map((optionId) => ({
            id: `option-${optionId}`,
            direction: "output",
            label: optionsById[optionId].digit,
            provides: "flow",
            maxConnections: 1,
        })),
        {
            id: "invalid",
            direction: "output",
            label: _t("Invalid"),
            provides: "flow",
            maxConnections: 1,
        },
        {
            id: "timeout",
            direction: "output",
            label: _t("Timeout"),
            provides: "flow",
            maxConnections: 1,
        },
        {
            id: "abort",
            direction: "output",
            label: _t("Abort"),
            provides: "flow",
            maxConnections: 1,
        },
    ];
    return {
        recordData: {
            id: ivr.id,
            display_name: ivr.display_name,
        },
        outputs,
        height: Math.max(200, 80 + outputs.length * 32),
    };
}

/**
 * Load a "Play Audio" node's two outputs.
 *
 * A "Play Audio" node is a Menu (voip.ivr) with one dial choice per key
 * (0-9, *, #), all wired to the same destination server-side (see
 * voip_call_flow.py's _sync_graph_ivrs), so it has no "invalid" or "abort"
 * branch worth showing and only needs the one "Skip" port here: "After"
 * (the "timeout" branch) fires once the message has played in full, "Skip"
 * fires the moment the caller presses any key.
 *
 * @param {Object} orm
 * @param {number} ivrId
 */
export async function loadAudioMessageNodeData(orm, ivrId) {
    const [ivr] = await orm.read("voip.ivr", [ivrId], ["display_name"]);
    return {
        recordData: {
            id: ivr.id,
            display_name: ivr.display_name,
        },
        outputs: [
            {
                id: "skip",
                direction: "output",
                label: _t("Skip"),
                provides: "flow",
                maxConnections: 1,
            },
            {
                id: "timeout",
                direction: "output",
                label: _t("After"),
                provides: "flow",
                maxConnections: 1,
            },
        ],
    };
}
