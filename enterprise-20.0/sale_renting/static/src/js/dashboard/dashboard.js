import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, proxy } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";

const CARD_FILTERS = [
    "filter_today",
    "rental_late_orders",
    "rental_pickups",
    "rental_returns",
    "rental_to_confirm",
    "rental_to_invoice",
];

export class Dashboard extends Component {
    static template = "sale_renting.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.state = proxy({
            counts: {
                today: 0,
                late: 0,
                pickups: 0,
                returns: 0,
                to_confirm: 0,
                to_invoice: 0,
            },
            selectedCards: new Set(),
        });

        useBus(this.env.searchModel, "update", () => this._syncSelectedCard());

        onWillStart(async () => {
            this._buildFilterIdMap();
            await this.loadCounts();
            this._syncSelectedCard();
        });
    }

    _buildFilterIdMap() {
        this.filterIds = {};
        for (const item of Object.values(this.env.searchModel.searchItems)) {
            if (item.type === "filter" && CARD_FILTERS.includes(item.name)) {
                this.filterIds[item.name] = item.id;
            }
        }
        for (const name of CARD_FILTERS) {
            if (!(name in this.filterIds)) {
                throw new Error(`Filter "${name}" not found in search model`);
            }
        }
    }

    _syncSelectedCard() {
        const activeIds = new Set(this.env.searchModel.query.map((q) => q.searchItemId));
        this.state.selectedCards = new Set(
            CARD_FILTERS.filter((name) => activeIds.has(this.filterIds[name]))
        );
    }

    get dashboardCardGroups() {
        return [
            {
                key: "left",
                cards: [
                    {
                        label: _t("Today"),
                        count: this.state.counts.today,
                        colorClass: "o_dashboard_card_today",
                        filter: "filter_today",
                    },
                    {
                        label: _t("Pickups"),
                        count: this.state.counts.pickups,
                        colorClass: "o_dashboard_card_pickups",
                        filter: "rental_pickups",
                    },
                    {
                        label: _t("Returns"),
                        count: this.state.counts.returns,
                        colorClass: "o_dashboard_card_returns",
                        filter: "rental_returns",
                    },
                    {
                        label: _t("Late"),
                        count: this.state.counts.late,
                        colorClass: "o_dashboard_card_late",
                        filter: "rental_late_orders",
                    },
                ],
            },
            {
                key: "right",
                cards: [
                    {
                        label: _t("To Confirm"),
                        count: this.state.counts.to_confirm,
                        colorClass: "o_dashboard_card_to_confirm",
                        filter: "rental_to_confirm",
                    },
                    {
                        label: _t("To Invoice"),
                        count: this.state.counts.to_invoice,
                        colorClass: "o_dashboard_card_to_invoice",
                        filter: "rental_to_invoice",
                    },
                ],
            },
        ];
    }

    async loadCounts() {
        this.state.counts = await this.orm
            .cache({
                type: "disk",
                update: "always",
                callback: (freshData, hasChanged) => {
                    if (hasChanged) {
                        this.state.counts = freshData;
                    }
                },
            })
            .call("sale.order", "retrieve_rental_dashboard");
    }

    onCardClick(filterName) {
        this.env.searchModel.toggleSearchItem(this.filterIds[filterName]);
    }

    getCardClass(card) {
        const isEmpty = card.count === 0;
        return [
            "o_dashboard_card",
            "btn",
            "flex-grow-1",
            "d-flex",
            "flex-column",
            "align-items-center",
            "justify-content-center",
            "py-2",
            "px-4",
            "lh-sm",
            isEmpty ? "o_dashboard_card_empty" : card.colorClass,
            this.state.selectedCards.has(card.filter) ? "active" : "",
        ]
            .filter(Boolean)
            .join(" ");
    }
}
