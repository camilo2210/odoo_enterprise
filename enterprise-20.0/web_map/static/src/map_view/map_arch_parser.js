import { unique } from "@web/core/utils/arrays";
import { exprToBoolean } from "@web/core/utils/strings";
import { visitXML } from "@web/core/utils/xml";
import { stringToOrderBy } from "@web/search/utils/order_by";
import { getActiveActions } from "@web/views/utils";

export class MapArchParser {
    parse(arch) {
        const archInfo = {
            fieldNames: [],
            popoverNode: undefined,
            popoverFieldNodes: [], // temporarily kept for backward compatibility
        };

        visitXML(arch, (node) => {
            switch (node.tagName) {
                case "map":
                    this.visitMap(node, archInfo);
                    break;
                case "field":
                    archInfo.fieldNames.push(node.getAttribute("name"));
                    archInfo.popoverFieldNodes.push({
                        fieldName: node.getAttribute("name"),
                        string: node.getAttribute("string"),
                    });
                    break;
                case "popover": {
                    archInfo.popoverNode = node;
                    return false;
                }
            }
        });

        archInfo.fieldNames = unique(archInfo.fieldNames);

        return archInfo;
    }

    visitMap(node, archInfo) {
        archInfo.activeActions = getActiveActions(node);
        archInfo.resPartnerField = node.getAttribute("res_partner");
        archInfo.fieldNames.push(archInfo.resPartnerField);

        if (node.hasAttribute("limit")) {
            archInfo.limit = parseInt(node.getAttribute("limit"), 10);
        }
        if (node.hasAttribute("routing")) {
            archInfo.routing = node.getAttribute("routing");
        }
        if (node.hasAttribute("hide_address")) {
            archInfo.hideAddress = exprToBoolean(node.getAttribute("hide_address"));
        }
        if (node.hasAttribute("hide_name")) {
            archInfo.hideName = exprToBoolean(node.getAttribute("hide_name"));
        }
        if (!archInfo.hideName) {
            archInfo.fieldNames.push("display_name");
        }
        if (node.hasAttribute("default_order")) {
            archInfo.defaultOrder = stringToOrderBy(node.getAttribute("default_order") || null);
        }
    }
}
