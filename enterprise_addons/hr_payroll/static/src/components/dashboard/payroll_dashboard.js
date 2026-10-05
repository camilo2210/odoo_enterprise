import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, proxy, status, useProps } from "@odoo/owl";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";

import { DashboardEmptyScreen } from "@hr_payroll/components/dashboard/dashboard_empty_screen/dashboard_empty_screen";
import { PayrollWarningCard } from "@hr_payroll/components/dashboard/payroll_warning_card/payroll_warning_card";
import { ArchiveWarningDialog } from "@hr_payroll/components/dashboard/payroll_warning_card/archive_warning_dialog";
import { toDateOnly, formatDateLabel } from "@hr_payroll/components/dashboard/utils";

const ANIMATION_FALLBACK_DELAY = 1000;
export const STORAGE_KEY_PREFIX = "hr_payroll.dashboard_warning_cache";

class PayrollDashboardComponent extends Component {
    static template = "hr_payroll.Dashboard";
    static components = {
        DashboardEmptyScreen,
        PayrollWarningCard,
    };
    props = useProps(standardActionServiceProps);

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = proxy({
            closingDatesData: [],
            warnings: [],
            mandatoryConfigId: null,
            isRecomputing: true,
            error: false,
        });
        this.toDateOnly = toDateOnly;
        this.formatDateLabel = formatDateLabel;
        this.storageKey = `${STORAGE_KEY_PREFIX}_${user.activeCompany?.id}_${user.userId}`;

        onMounted(() => this.loadDashboardData());

        onWillUnmount(() => this.warningStreamAbort?.abort());
    }

    async startWarningStream(warningIds) {
        const streamedIds = new Set();
        const reconciles = [];
        let previousId = null;
        let cardsForId = [];
        this.warningStreamAbort = new AbortController();
        let completed = false;

        const flushCardsForId = () => {
            if (previousId !== null) {
                reconciles.push(this.reconcileWarnings(cardsForId, previousId));
            }
            cardsForId = [];
        };
        
        try {
            const url = `/hr_payroll/dashboard/warnings`;
            const response = await fetch(url, { signal: this.warningStreamAbort.signal });
            if (!response.ok) {
                throw new Error(`Warning stream answered with HTTP ${response.status}`);
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            while (!completed && status(this) !== "destroyed") {
                const { done: streamEnded, value } = await reader.read();
                if (streamEnded) {
                    break;
                }
                buffer += decoder.decode(value, { stream: true });
                let index;
                while ((index = buffer.indexOf("\n")) !== -1) {
                    const line = buffer.slice(0, index).trim();
                    buffer = buffer.slice(index + 1);
                    if (!line) {
                        continue;
                    }
                    const payload = JSON.parse(line);
                    if (payload.type === "card") {
                        const card = {
                            ...payload.warning,
                            key: `${payload.warning.key}_${payload.warning.warning_date}`,
                            is_loading: false,
                        };
                        streamedIds.add(card.id);
                        if (card.id !== previousId) {
                            flushCardsForId();
                            previousId = card.id;
                        }
                        cardsForId.push(card);
                    } else if (payload.type === "done") {
                        completed = true;
                        flushCardsForId();
                        break;
                    }
                }
            }
        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }
            console.warn("Could not load the payroll dashboard warnings", error);
        }

        await Promise.all(reconciles);
        if (status(this) === "destroyed") {
            return;
        }
        if (completed) {
            // A warning id that never appeared in the stream has nothing left to show.
            const silentIds = warningIds.filter((id) => !streamedIds.has(id));
            await Promise.all(silentIds.map((id) => this.reconcileWarnings([], id)));
        } else {
            this.state.error = true;
        }
    }

    retryWarningStream() {
        this.state.error = false;
        this.runWarningStream(this.lastWarningIds || []);
    }

    async loadDashboardData() {
        for (const card of this._readStoredWarnings()) {
            this.mergeWarning({
                ...card,
                is_loading: true,
            });
        }

        const initialData = await this.orm.silent.call(
            "hr.payroll.warning",
            "get_payroll_dashboard_data",
            []
        );
        if (status(this) === "destroyed") {
            return;
        }
        this.state.closingDatesData = initialData.closing_dates_data || [];
        this.state.mandatoryConfigId = initialData.mandatory_config_id;

        const warningIds = initialData.warning_ids || [];
        const staleWarnings = this.state.warnings.filter((w) => !warningIds.includes(w.id));
        await Promise.all(staleWarnings.map((warning) => this.fadeOutWarning(warning)));
        this.lastWarningIds = warningIds;
        await this.runWarningStream(warningIds);
    }

    async runWarningStream(warningIds) {
        this.state.isRecomputing = true;
        await this.startWarningStream(warningIds);
        if (status(this) !== "destroyed") {
            this.state.isRecomputing = false;
            this._saveToLocalStorage();
        }
    }

    _readStoredWarnings() {
        try {
            const raw = browser.localStorage.getItem(this.storageKey);
            const parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed)
                ? parsed.filter((card) => card && typeof card.id === "number" && typeof card.warning_date === "string")
                : [];
        } catch {
            return [];
        }
    }

    _saveToLocalStorage() {
        const cacheableWarnings = this.state.warnings
            .map((warning) => ({
                id: warning.id,
                key: warning.key,
                name: warning.name,
                description: warning.description,
                color_class: warning.color_class,
                button_name: warning.button_name,
                warning_date: warning.warning_date,
            }));
        browser.localStorage.setItem(this.storageKey, JSON.stringify(cacheableWarnings));
    }

    mergeWarning(warning) {
        if (!warning || status(this) === "destroyed") {
            return;
        }
        this.state.warnings.push(warning);
    }

    removeWarning(warning) {
        const index = this.state.warnings.indexOf(warning);
        if (index !== -1) {
            this.state.warnings.splice(index, 1);
        }
    }

    /**
     * Syncs the cards currently displayed for `warningId` with `recomputedCards`,
     * matching them by warning_date: a card still present is updated in place
     * (e.g. its loading spinner resolves into real data), a displayed card missing
     * from `recomputedCards` is faded out, and a card in `recomputedCards` with no
     * displayed match is faded in.
     */
    async reconcileWarnings(recomputedCards, warningId) {
        const oldWarnings = this.state.warnings.filter(w => w.id === warningId);
        const unmatchedCards = [...recomputedCards];

        for (const warning of oldWarnings) {
            const matchIndex = unmatchedCards.findIndex(c => c.warning_date === warning.warning_date);
            if (matchIndex !== -1) {
                const [recomputed] = unmatchedCards.splice(matchIndex, 1);
                Object.assign(warning, recomputed, { key: warning.key });
            } else {
                await this.fadeOutWarning(warning);
            }
        }
        // handle new warnings
        for (const card of unmatchedCards) {
            await this.fadeInWarning(card);
        }
    }

    async fadeOutWarning(warning) {
        warning.is_fading_out = true;
        await this._waitForAnimationEnd(warning.key);
        this.removeWarning(warning);
    }

    async fadeInWarning(card) {
        card.is_fading_in = true;
        this.mergeWarning(card);
        await this._waitForAnimationEnd(card.key);
        card.is_fading_in = false;
    }

    /**
     * Waits for the animationend event on the element identified by `key`.
     * The element may not be mounted yet so this
     * retries every frame until it appears, still bounded by the same
     * ANIMATION_FALLBACK_DELAY safety net used for the animation itself.
     */
    _waitForAnimationEnd(key) {
        return new Promise((resolve) => {
            const deadline = Date.now() + ANIMATION_FALLBACK_DELAY;
            const waitForElement = () => {
                const el = document.querySelector(`[data-warning-key="${CSS.escape(key)}"]`);
                if (el) {
                    listenForAnimationEnd(el);
                    return;
                }
                if (Date.now() >= deadline) {
                    resolve();
                    return;
                }
                requestAnimationFrame(waitForElement);
            };

            const listenForAnimationEnd = (el) => {
                const done = () => {
                    clearTimeout(timeoutId);
                    resolve();
                };
                const timeoutId = setTimeout(done, Math.max(0, deadline - Date.now()));
                el.addEventListener("animationend", done, { once: true });
            };
            waitForElement();
        });
    }

    getDateLabelClasses(date) {
        return date > luxon.DateTime.now() ? "text-normal" : "text-danger";
    }

    get groupedWarnings() {
        const grouped = {};
        for (const warning of this.state.warnings) {
            const dateObj = luxon.DateTime.fromISO(warning.warning_date);
            const firstDayMonth = dateObj.startOf("month");
            const dateKey = warning.warning_date;

            if (!grouped[firstDayMonth]) {
                grouped[firstDayMonth] = { date: firstDayMonth, warningDates: [], warningsByDate: {} };
            }
            if (!grouped[firstDayMonth].warningsByDate[dateKey]) {
                grouped[firstDayMonth].warningsByDate[dateKey] = [];
                grouped[firstDayMonth].warningDates.push(dateObj);
            }
            grouped[firstDayMonth].warningsByDate[dateKey].push(warning);
        }

        const groups = Object.values(grouped);
        for (const group of groups) {
            group.warningDates.sort((a, b) => a - b);
        }
        return groups.sort((a, b) => a.date - b.date);
    }

    actionArchive = (id, title) => {
        this.dialog.add(ArchiveWarningDialog, {
            resId: id,
            warningTitle: title,
            close: this.dialog.closeAll,

            onDismiss: async (dismissedId) => {
                const dismissed = this.state.warnings.filter((w) => w.id === dismissedId);
                await Promise.all(dismissed.map((warning) => this.fadeOutWarning(warning)));
                if (status(this) !== "destroyed") {
                    this._saveToLocalStorage();
                }
            },
        });
    };
}

registry.category("actions").add("hr_payroll_dashboard", PayrollDashboardComponent);

export default PayrollDashboardComponent;
