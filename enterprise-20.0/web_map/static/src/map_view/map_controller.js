import { _t } from "@web/core/l10n/translation";
import { loadJS, loadCSS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";
import { useModel } from "@web/model/model";
import { standardViewProps } from "@web/views/standard_view_props";
import { useSetupAction } from "@web/search/action_hook";
import { Layout } from "@web/search/layout";
import { usePager } from "@web/search/pager_hook";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { useSearchBarToggler } from "@web/search/search_bar/search_bar_toggler";
import { CogMenu } from "@web/search/cog_menu/cog_menu";

import { Component, onWillUnmount, onWillStart, proxy, status, t, useProps } from "@odoo/owl";

export class MapController extends Component {
    static template = "web_map.MapView";
    static components = {
        Layout,
        SearchBar,
        CogMenu,
    };
    props = useProps({
        ...standardViewProps,
        archInfo: t.object(),
        Model: t.function(),
        modelParams: t.object(),
        Renderer: t.function(),
        buttonTemplate: t.string(),
    });

    setup() {
        this.action = useService("action");

        /** @type {typeof MapModel} */
        const Model = this.props.Model;
        this.model = proxy(useModel(Model, this.props.modelParams));

        onWillUnmount(() => {
            this.model.geolocation.stopFetchingCoordinates();
        });

        useSetupAction({
            getLocalState: () => this.model.exportedState,
        });

        onWillStart(() =>
            Promise.all([
                loadJS("/web_map/static/lib/leaflet/leaflet.js"),
                loadCSS("/web_map/static/lib/leaflet/leaflet.css"),
            ])
        );

        usePager(() => ({
            offset: this.model.metaData.offset,
            limit: this.model.metaData.limit,
            total: this.model.data.count,
            onUpdate: ({ offset, limit }) => this.model.load({ offset, limit }),
        }));
        this.searchBarToggler = useSearchBarToggler();
    }

    /**
     * @returns {any}
     */
    get rendererProps() {
        return {
            model: this.model,
            onMarkerClick: this.openRecords.bind(this),
        };
    }

    get canCreate() {
        return this.props.archInfo.activeActions.create;
    }

    /**
     * Returns the [id, type] tuples for the given view types, using the ids
     * defined on the action if any.
     *
     * @param {...string} viewTypes
     * @returns {Array<[number|false, string]>}
     */
    _getActionViews(...viewTypes) {
        const { views = [] } = this.env.config;
        return viewTypes.map((viewType) => {
            const view = views.find((v) => v[1] === viewType);
            return [view ? view[0] : false, viewType];
        });
    }

    /**
     * Redirects to views when clicked on open button in marker popup.
     *
     * @param {number[]} ids
     * @param {'new_window'|'dialog'|'current'} [target='current']
     * @returns {Promise<any>}
     */
    openRecords(ids, target = "current") {
        let actionRequest = {
            type: "ir.actions.act_window",
            name: this.env.config.getDisplayName() || _t("Untitled"),
            res_model: this.props.resModel,
        };
        let options = {};
        if (target === "new_window") {
            options.newWindow = true;
        }
        if (ids.length > 1) {
            actionRequest = {
                ...actionRequest,
                domain: [["id", "in", ids]],
                views: this._getActionViews("list", "form"),
            };
        } else {
            actionRequest = {
                ...actionRequest,
                views: this._getActionViews("form"),
                res_id: ids[0],
            };
        }
        if (target === "dialog") {
            actionRequest = {
                ...actionRequest,
                target: "new",
            };
            if (ids.length === 1) {
                const record = this.model.data.unlocatedRecords?.find(({ id }) => id === ids[0]);
                if (record) {
                    actionRequest.name = record.display_name;
                }
            }
            options = {
                ...options,
                onClose: (onCloseInfo) => {
                    if (status(this) !== "destroyed" && !onCloseInfo?.noReload) {
                        this.model.load({});
                    }
                },
            };
        }
        return this.action.doAction(actionRequest, options);
    }
}
