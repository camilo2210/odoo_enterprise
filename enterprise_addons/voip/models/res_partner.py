import unicodedata

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.tools.sql import escape_like_value

from odoo.addons.mail.tools.discuss import Store

"""
    █
    █
    █
┌────────────────────────┐
│ ██████████████████████ │
│ █      10:22 PM      █ │
│ █     YO LA TEAM     █ │
│ ██████████████████████ │  T9 "ENCODING" (ITU E.161)
│                        │  =========================
│ ╔══════╦══════╦══════╗ │
│ ║  1   ║  2   ║  3   ║ │  Each letter of the Latin alphabet is mapped to a
│ ║      ║ ABC  ║ DEF  ║ │  number, which is used to encode a word using only
│ ╠══════╬══════╬══════╣ │  digits, like on an old cell phone keypad.
│ ║  4   ║  5   ║  6   ║ │
│ ║ GHI  ║ JKL  ║ MNO  ║ │
│ ╠══════╬══════╬══════╣ │
│ ║  7   ║  8   ║  9   ║ │
│ ║ PQRS ║ TUV  ║ WXYZ ║ │
│ ╠══════╬══════╬══════╣ │
│ ║  *   ║  0   ║  #   ║ │
│ ║      ║      ║      ║ │
│ ╚══════╩══════╩══════╝ │
└────────────────────────┘
"""
T9_MAPPING = {
    letter: digit
    for letters, digit in [
        ("abc", "2"),
        ("def", "3"),
        ("ghi", "4"),
        ("jkl", "5"),
        ("mno", "6"),
        ("pqrs", "7"),
        ("tuv", "8"),
        ("wxyz", "9"),
    ]
    for letter in letters
}

LIGATURES = {
    "Æ": "Ae",
    "æ": "ae",
    "Œ": "Oe",
    "œ": "oe",
    "Ĳ": "IJ",
    "ĳ": "ij",
}


def expand_ligatures(text):
    for ligature, replacement in LIGATURES.items():
        text = text.replace(ligature, replacement)
    return text


def unaccent(text):
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if unicodedata.category(c) != "Mn"
    )


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = [
        "res.partner",
        "voip.pbx.destination.mixin",
        "voip.phone.country.mixin",
        "voip.activity.mixin",
    ]

    t9_name = fields.Char(
        compute="_compute_t9_name",
        export_string_translation=False,
        help=(
            "The partner's name, encoded as the digits that correspond to the letters on an old cell phone keypad.\n"
            "Useful for searching for partners based on this field.\n"
            "Spaces are preserved, characters that can't be encoded are replaced with an 'x'.\n"
            "T9 stands for Text on 9 keys, it comes from the name of the original technology on old cell phones."
        ),
        store=True,
    )

    @api.depends("name")
    def _compute_t9_name(self):
        def encode(letter):
            if letter in T9_MAPPING:
                return T9_MAPPING[letter]
            if letter in "0123456789 ":
                return letter
            return "x"

        for partner in self:
            if not partner.name:
                partner.t9_name = False
                continue
            normalized_name = expand_ligatures(unaccent(partner.name)).casefold()
            partner.t9_name = "".join(encode(letter) for letter in normalized_name)
            # Add a space at the beginning so you can search for matches at the
            # beginning of each word using a pattern like '% 234%'.
            partner.t9_name = " " + partner.t9_name

    def _search_commercial_partners(self, active_test=True):
        """Return all partners belonging to self's commercial entity, the
        commercial entity itself included.
        """
        self.ensure_one()
        return self.env["res.partner"].with_context(active_test=active_test).search(
            [("id", "child_of", self.commercial_partner_id.id)],
        )

    @api.model
    def get_contacts(self, offset, limit, search_terms, internal_users_first=False, prioritized_contacts_limit=0):
        """Fetch VoIP contacts matching the search and pagination parameters.

        When ``prioritized_contacts_limit`` is non-zero, up to that many
        matching contacts are selected by the VoIP call model and inserted
        before the regular contact search results. The returned page is then
        computed from that combined list, so ``offset`` and ``limit`` apply as
        if prioritized contacts were the first rows of the result set. In that
        mode, the response also includes all prioritized contact ids so the
        client can keep the same ordering while filtering already-loaded
        contacts locally. See ``_get_prioritized_contacts`` (e.g. getting
        recently called partners first).
        """
        domain = Domain("phone", "!=", False)
        if search_terms:
            escaped_search_terms = escape_like_value(search_terms)
            subdomain = Domain("complete_name", "ilike", escaped_search_terms) | Domain("email", "ilike", escaped_search_terms)
            if len(search_terms) >= self._phone_search_min_length:
                subdomain |= Domain("phone_mobile_search", "like", escaped_search_terms)
            subdomain |= Domain("t9_name", "ilike", f" {escaped_search_terms}")
            domain &= subdomain

        search_kwargs = {"offset": offset, "limit": limit}
        if internal_users_first:
            search_kwargs["order"] = f"partner_share ASC, {self._order}"

        if not prioritized_contacts_limit:
            contacts = self.search(domain, **search_kwargs)
            return Store().add(contacts, "_store_voip_fields")

        prioritized_contacts = self.env["voip.call"]._get_prioritized_contacts(
            domain,
            limit=prioritized_contacts_limit,
        )
        if prioritized_contacts:
            domain &= Domain("id", "not in", prioritized_contacts.ids)
        if offset < len(prioritized_contacts):
            prioritized_contacts_page = prioritized_contacts[offset:offset + limit]
            search_kwargs["offset"] = 0
            search_kwargs["limit"] = limit - len(prioritized_contacts_page)
        else:
            prioritized_contacts_page = self.env["res.partner"]
            search_kwargs["offset"] = offset - len(prioritized_contacts)
        contacts = self.search(domain, **search_kwargs) if search_kwargs["limit"] else self.env["res.partner"]
        return {
            "store_data": Store().add(prioritized_contacts_page | contacts, "_store_voip_fields"),
            "prioritized_contact_ids": prioritized_contacts.ids,
        }

    def _store_voip_fields(self, res: Store.FieldList):
        res.extend(["complete_name", "parent_name", "email", "function", "is_company", "name", "phone", "phone_formatted", "partner_share"])
        self._store_im_status_fields(res)
        res.one("phone_country_id", "_store_voip_fields")
        res.attr("t9_name")
