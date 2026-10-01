from lxml import etree

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.partner_identifiers import TIN_CATEGORIES


UY_RUT_DGI_CODE = 2
UY_FOREIGN_ID_DGI_CODE = 4  # Otro
UY_FOREIGN_COUNTRY_DGI_CODE = 6
UY_FOREIGN_VAT_DGI_CODE = 7  # NIFE

UY_DGI_CODES = {
    'UY_NIE': 1,
    'UY_CI': 3,
    'UY_OTR': 4,
    'PASSPORT': 5,
    'UY_DNI': 6,
    'UY_NIFE': 7,
}
DGI_FOREIGN_COUNTRY_CODES = {'AR', 'BR', 'CL', 'PY'}  # those countries must be handled specifically with DGI as per specification


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _l10n_uy_edi_get_dgi_code(self):
        """ Return the DGI code that identifies the partner's document type on a CFE,
        derived from its preferred legal entity identifier.
        """
        vals = self._get_preferred_legal_entity_identifier_vals()
        if dgi_code := UY_DGI_CODES.get(vals.get('key')):
            return dgi_code
        if vals.get('category') in TIN_CATEGORIES:
            countries = set(vals.get('countries') or [])
            if 'UY' in countries:
                return UY_RUT_DGI_CODE
            if countries & DGI_FOREIGN_COUNTRY_CODES:
                return UY_FOREIGN_COUNTRY_DGI_CODE
            return UY_FOREIGN_VAT_DGI_CODE
        return UY_FOREIGN_ID_DGI_CODE if vals else 0

    def _l10n_uy_edi_get_fiscal_address(self):
        res = [self[fieldname] for fieldname in ["street", "street2"] if self[fieldname]]
        return " ".join(res)[:70]

    def button_l10n_uy_populate_from_vat(self):
        """ Fetch partner details from DGI by RUT and write them to the partner.
        Every mapped field is always written, missing values are set to False to not mix
        potentially wrong, existing data with the new data. """
        self.ensure_one()
        if not self.vat or self.country_code != 'UY':
            return False

        response = self.env["l10n_uy_edi.document"]._ucfe_inbox("640", {"RutEmisor": self.vat})
        if response.get("errors"):
            raise UserError("\n - ".join(response["errors"]))

        xml_string = response["response"].findtext(".//{*}XmlCfeFirmado")
        if not xml_string:
            return False

        info = etree.fromstring(xml_string.encode())
        contact_xpath = ".//{*}WS_Domicilio.WS_DomicilioItem.Contacto[{*}TipoCtt_Des='%s']/{*}DomCtt_Val"
        xpaths = {
            "name": ".//{*}Denominacion",
            "ref": ".//{*}NombreFantasia",
            "street2": ".//{*}Dom_Coment",
            "city": ".//{*}Loc_Nom",
            "zip": ".//{*}Dom_Pst_Cod",
            "phone": contact_xpath % "TELEFONO FIJO",
            "email": contact_xpath % "CORREO ELECTRONICO",
        }
        values = {field: info.findtext(xpath) or False for field, xpath in xpaths.items()}
        if values["zip"] == "0":  # DGI sends 0 when no postal code is on file
            values["zip"] = False

        street_part_xpaths = (".//{*}Calle_Nom", ".//{*}Dom_Pta_Nro", ".//{*}Dom_Bis_Flg", ".//{*}Dom_Ap_Nro")
        street_parts = [info.findtext(xp) for xp in street_part_xpaths]
        values["street"] = " ".join(part for part in street_parts if part) or False
        state = self.env["l10n_uy_edi.document"]._l10n_uy_get_state_by_name(info.findtext(".//{*}Dpto_Nom"))
        values["state_id"] = state.id if state else False
        self.write(values)
