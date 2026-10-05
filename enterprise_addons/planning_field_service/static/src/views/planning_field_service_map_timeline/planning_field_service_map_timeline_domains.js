import { Domain } from "@web/core/domain";

/**
 * Widens a domain to also match open shifts (records with no resource
 * assigned), regardless of any resource_ids/department_id/manager_id leaf
 * it may already contain.
 *
 * @param {any[]} domain
 * @returns {Domain}
 */
export function getOpenShiftsDomain(domain) {
    return Domain.and([
        Domain.removeDomainLeaves(domain, ["resource_ids", "department_id", "manager_id"]),
        [["resource_ids", "=", false]],
    ]);
}
