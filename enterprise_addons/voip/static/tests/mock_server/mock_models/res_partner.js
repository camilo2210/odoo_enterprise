import { mailModels } from "@mail/../tests/mail_test_helpers";
import { Store } from "@mail/../tests/mock_server/store";

import { fields, getKwArgs, makeKwArgs } from "@web/../tests/web_test_helpers";

const T9_MAPPING = {};
for (const [letters, digit] of [
    ["abc", "2"],
    ["def", "3"],
    ["ghi", "4"],
    ["jkl", "5"],
    ["mno", "6"],
    ["pqrs", "7"],
    ["tuv", "8"],
    ["wxyz", "9"],
]) {
    for (const letter of letters) {
        T9_MAPPING[letter] = digit;
    }
}
const T9_LIGATURES = { Æ: "Ae", æ: "ae", Œ: "Oe", œ: "oe", Ĳ: "IJ", ĳ: "ij" };

export class ResPartner extends mailModels.ResPartner {
    _order = "complete_name ASC, id DESC";

    t9_name = fields.Char({ compute: "_compute_t9_name" });
    phone_sanitized = fields.Char();
    phone_formatted = fields.Char();

    _compute_complete_name() {
        super._compute_complete_name();
        for (const partner of this) {
            partner.complete_name ||= "";
        }
    }

    _compute_t9_name() {
        for (const partner of this) {
            if (!partner.name) {
                partner.t9_name = false;
                continue;
            }
            let text = partner.name;
            for (const [ligature, replacement] of Object.entries(T9_LIGATURES)) {
                text = text.replaceAll(ligature, replacement);
            }
            text = text
                .normalize("NFKD")
                .replace(/\p{Mn}/gu, "")
                .toLowerCase();
            const encoded = Array.from(text)
                .map((char) => T9_MAPPING[char] ?? ("0123456789 ".includes(char) ? char : "x"))
                .join("");
            partner.t9_name = ` ${encoded}`;
        }
    }

    /**
     * @param {number} offset
     * @param {number} limit
     * @param {string} search_terms
     * @param {boolean} internal_users_first
     * @param {number} prioritized_contacts_limit
     */
    get_contacts(offset, limit, search_terms, internal_users_first, prioritized_contacts_limit) {
        const kwargs = getKwArgs(
            arguments,
            "offset",
            "limit",
            "search_terms",
            "internal_users_first",
            "prioritized_contacts_limit"
        );
        offset = kwargs.offset || 0;
        limit = kwargs.limit || 0;
        search_terms = kwargs.search_terms || "";
        internal_users_first = kwargs.internal_users_first || false;
        prioritized_contacts_limit = kwargs.prioritized_contacts_limit || 0;

        const domain = [["phone", "!=", false]];
        if (search_terms) {
            // py searches phone_mobile_search (gated by _phone_search_min_length),
            // which covers the raw phone fields and phone_sanitized; the mock has no
            // such field, so it matches the raw phone and phone_sanitized with no min
            // length (the dialer matches phone prefixes, e.g. a single digit in the
            // keypad).
            const subdomain = [
                "|",
                "|",
                "|",
                "|",
                ["complete_name", "ilike", search_terms],
                ["email", "ilike", search_terms],
                ["phone", "like", search_terms],
                ["phone_sanitized", "like", search_terms],
                ["t9_name", "ilike", ` ${search_terms}`],
            ];
            domain.push(...subdomain);
        }
        const order = internal_users_first ? `partner_share ASC, ${this._order}` : undefined;
        if (!prioritized_contacts_limit) {
            const contacts = this.browse(this.search(domain, makeKwArgs({ offset, limit, order })));
            return new Store().add(contacts, "_store_voip_fields").as_dict();
        }
        const prioritizedContactIds = this.env["voip.call"]._get_prioritized_contact_ids(
            domain,
            prioritized_contacts_limit
        );
        if (prioritizedContactIds.length) {
            domain.push(["id", "not in", prioritizedContactIds]);
        }
        let prioritizedContactPageIds = [];
        if (offset < prioritizedContactIds.length) {
            prioritizedContactPageIds = prioritizedContactIds.slice(offset, offset + limit);
            offset = 0;
            limit -= prioritizedContactPageIds.length;
        } else {
            offset -= prioritizedContactIds.length;
        }
        const contactIds = limit ? this.search(domain, makeKwArgs({ offset, limit, order })) : [];
        return {
            store_data: new Store()
                .add(
                    this.browse([...prioritizedContactPageIds, ...contactIds]),
                    "_store_voip_fields"
                )
                .as_dict(),
            prioritized_contact_ids: prioritizedContactIds,
        };
    }

    _store_voip_fields(res) {
        res.extend([
            "parent_name",
            "email",
            "function",
            "is_company",
            "name",
            "phone",
            "phone_formatted",
            "partner_share",
        ]);
        res.attr("complete_name", (contact) => contact.complete_name || contact.name); // mock: fall back to name
        this._store_im_status_fields(res);
        res.one("phone_country_id", "_store_voip_fields");
        res.attr("t9_name");
    }
}
