import { DomainSelector } from "@web/core/domain_selector/domain_selector";

export class MarketingDomainSelector extends DomainSelector {
    getShowArchivedCheckBox(hasActiveField, props) {
        return false;
    }
}
