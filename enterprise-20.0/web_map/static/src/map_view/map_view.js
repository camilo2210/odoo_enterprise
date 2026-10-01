import { registry } from "@web/core/registry";
import { MapArchParser } from "./map_arch_parser";
import { MapModel } from "./map_model";
import { MapController } from "./map_controller";
import { MapRenderer } from "./map_renderer";

export const mapView = {
    type: "map",

    Controller: MapController,
    Renderer: MapRenderer,
    Model: MapModel,
    ArchParser: MapArchParser,

    buttonTemplate: "web_map.MapView.Buttons",

    props: (genericProps, view, config) => {
        let modelParams = genericProps.state;
        const { arch, resModel, fields, context, limit } = genericProps;
        const archInfo = new view.ArchParser().parse(arch);
        if (!modelParams) {
            const views = config.views || [];
            modelParams = {
                canEdit: archInfo.activeActions.edit,
                context,
                defaultOrder: archInfo.defaultOrder,
                fieldNames: archInfo.fieldNames,
                popoverFieldNodes: archInfo.popoverFieldNodes,
                popoverNode: archInfo.popoverNode,
                fields,
                hasFormView: views.some((view) => view[1] === "form"),
                hideAddress: archInfo.hideAddress || false,
                hideName: archInfo.hideName || false,
                limit: archInfo.limit || limit || 80,
                offset: 0,
                resModel,
                resPartnerField: archInfo.resPartnerField,
                routing: archInfo.routing || false,
            };
        }

        return {
            ...genericProps,
            archInfo,
            Model: view.Model,
            modelParams,
            Renderer: view.Renderer,
            buttonTemplate: view.buttonTemplate,
        };
    },
};

registry.category("views").add("map", mapView);
