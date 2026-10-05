# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


class PosLoadMixin(models.AbstractModel):
    _inherit = "pos.load.mixin"

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return False

    @api.model
    def _load_pos_preparation_data_fields(self):
        return []

    @api.model
    def _load_pos_preparation_data_read(self, data):
        """ Read specific fields from the given records """
        return self.read(data['fields'])

    @api.model
    def _load_prep_data_domain_and_dependencies(self, data):
        adapted_data = {model: d['records'] for model, d, in data.items()}
        fields = self._load_pos_preparation_data_fields()
        return {
            'domain': self._load_pos_preparation_data_domain(adapted_data),
            'fields': fields,
            'relations': self._load_data_relations(fields),
        }

    @api.model
    def _load_prep_metadata(self, data):
        result = self._load_prep_data_domain_and_dependencies(data)
        data[self._name] = {
            **result,
            'records': self.search(domain=result['domain']),
        }

    @api.model
    def _read_prep_data_from_metadata(self, server_data):
        response = {}
        for model, data in server_data.items():
            try:
                records = data['records']
                response[model] = {
                    **data,
                    'records': records._load_pos_preparation_data_read(data) if len(records) > 0 else [],
                }
            except AccessError as e:
                response[model] = []
                _logger.info("Could not load model %s due to AccessError: %s", model, e)

        return response
