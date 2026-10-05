import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

export class ServiceRequestsForm extends Interaction {
    static selector = ".o_service_requests_form";
    dynamicContent = {
        'select[name="country_id"]': { "t-on-change": this.onCountryChange },
    };

    setup() {
        this.countryEl = this.el.querySelector('select[name="country_id"]');
        this.stateEl = this.el.querySelector('select[name="state_id"]');
        this.roleEl = this.el.querySelector('select[name="role_id"]');
        this.phoneEl = this.el.querySelector('input[name="partner_phone"]');
    }

    async willStart() {
        const data = await this.waitFor(rpc("/service-requests/setup"));
        this._fillSelect(this.countryEl, data.countries);
        this._fillSelect(this.roleEl, data.planning_roles);
        if (data.google_places_enabled) {
            const streetEl = this.el.querySelector('input[name="street"]');
            if (streetEl) {
                streetEl.dataset.autocompleteEnabled = "1";
                this.services["public.interactions"].startInteractions(this.el);
            }
        }
        if (data.prefill.country_id) {
            if (this.countryEl) {
                this.countryEl.value = data.prefill.country_id;
            }
            await this._loadCountry(data.prefill.country_id, data.prefill.state_id);
        }
    }

    async onCountryChange() {
        const countryId = parseInt(this.countryEl.value);
        if (countryId === this.lastCountryId) {
            return;
        }
        await this._loadCountry(countryId);
    }

    async _loadCountry(countryId, prefillStateId = null) {
        if (!countryId) {
            this.lastCountryId = null;
            this._fillSelect(this.stateEl, []);
            if (this.stateEl) {
                this.stateEl.disabled = true;
            }
            if (this.phoneEl) {
                this.phoneEl.placeholder = "";
            }
            return;
        }
        this.lastCountryId = countryId;
        const data = await this.waitFor(rpc(`/website/country_infos/${countryId}`));
        if (countryId !== this.lastCountryId) {
            return;
        }
        this._fillSelect(
            this.stateEl,
            data.states.map(([id, name]) => ({ id, name }))
        );
        if (this.stateEl) {
            if (prefillStateId) {
                this.stateEl.value = prefillStateId;
            }
            this.stateEl.disabled = data.states.length === 0;
        }
        if (this.phoneEl) {
            this.phoneEl.placeholder = data.phone_code ? `+${data.phone_code}` : "";
        }
    }

    _fillSelect(selectEl, records) {
        selectEl?.replaceChildren(
            selectEl.firstElementChild,
            ...records.map((r) => new Option(r.name, r.id))
        );
    }
}

registry
    .category("public.interactions")
    .add("website_planning_field_service.service_requests_form", ServiceRequestsForm);
