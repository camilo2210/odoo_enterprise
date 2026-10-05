# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
import requests
from lxml import etree

from odoo import fields, models
from odoo.addons.account.tools import LegacyHTTPAdapter


class ResCompany(models.Model):
    _inherit = "res.company"

    def _l10n_tr_uses_buy_rate(self):
        self.ensure_one()
        return self.currency_provider == "tcmb"

    def _parse_tcmb_data(self, available_currencies):
        # OVERRIDE: also parses the buying rate, in addition to the selling rate.
        server_url = "https://www.tcmb.gov.tr/kurlar/today.xml"
        available_currency_names = set(available_currencies.mapped("name"))

        # LegacyHTTPAdapter is used as connecting to the url raises an SSL error "unsafe legacy renegotiation disabled".
        # This happens with OpenSSL 3.0 when trying to connect to legacy websites that disable renegotiation without signaling it correctly.
        session = requests.Session()
        session.mount("https://", LegacyHTTPAdapter())

        res = session.get(server_url, timeout=30)
        res.raise_for_status()

        root = etree.fromstring(res.text.encode())
        rate_date = fields.Date.to_string(datetime.datetime.strptime(root.attrib["Date"], "%m/%d/%Y"))

        rslt = {}
        for currency in root:
            code = currency.attrib["Kod"]
            if code not in available_currency_names:
                continue
            # Sell rate is the default rate
            rslt[code] = (1 / float(currency.find("ForexSelling").text), rate_date)
            rslt[f"{code}_buy"] = (1 / float(currency.find("ForexBuying").text), rate_date)
        rslt["TRY"] = (1.0, rate_date)
        rslt["TRY_buy"] = (1.0, rate_date)

        return rslt

    def _generate_currency_rates(self, parsed_data):
        # EXTENDS: also parses the buying rate to store on the currency rate record.
        # Also stripping the _buy keys to avoid regressions
        buy_data = {code: parsed_data.pop(code) for code in list(parsed_data) if code.endswith("_buy")}
        super()._generate_currency_rates(parsed_data)

        if not buy_data:
            return

        currency_names = [code.removesuffix("_buy") for code in buy_data]
        rate_date = next(iter(buy_data.values()))[1]
        for company in self:
            base_buy_rate_entry = buy_data.get(f"{company.currency_id.name}_buy")
            if not base_buy_rate_entry:
                continue
            base_buy_rate = base_buy_rate_entry[0]

            domain = [("currency_id.name", "in", currency_names), ("name", "=", rate_date), ("company_id", "=", company.id)]
            rate_currency_map = {
                curr.name: curr_rate
                for curr, curr_rate in self.env["res.currency.rate"]._read_group(domain, groupby=["currency_id"], aggregates=["id:recordset"])
            }
            for code, (l10n_tr_buy_rate, _date) in buy_data.items():
                rate_record = rate_currency_map.get(code.removesuffix("_buy"))
                if rate_record:
                    rate_record.l10n_tr_buy_rate = l10n_tr_buy_rate / base_buy_rate
