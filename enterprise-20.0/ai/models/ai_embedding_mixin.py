# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from collections import defaultdict

from odoo import api, fields, models
from odoo.fields import Domain

from odoo.addons.ai.utils.ai_text_tools import chunk_text

_logger = logging.getLogger(__name__)


class AIEmbeddingMixin(models.AbstractModel):
    _name = "ai.embedding.mixin"
    _description = "AI Embedding Mixin"
    _explanation = "A mixin that contains the generic methods for all models that need to be embedded."

    embedding_ids = fields.One2many(
        "ai.embedding",
        "res_id",
        string="Record embedding ids",
    )
    embedding_status = fields.Selection(
        string="Embedding Status",
        selection=[
            ("processing", "Processing"),
            ("indexed", "Indexed"),
            ("dirty", "Dirty"),
            ("failed", "Failed"),
        ],
        default="processing",
        compute="_compute_embedding_status",
        store=True,
    )

    @api.depends("embedding_ids.embedding_vector", "embedding_ids.has_embedding_generation_failed")
    def _compute_embedding_status(self):
        for record in self:
            embedding_ids = record.embedding_ids
            if embedding_ids and any(e.has_embedding_generation_failed for e in embedding_ids):
                record.embedding_status = "failed"
            elif not embedding_ids or not all(e.embedding_vector for e in embedding_ids):
                record.embedding_status = "processing"
            else:
                record.embedding_status = "indexed"

    @api.ondelete(at_uninstall=False)
    def _unlink_embeddings(self):
        """Unlinks the linked embeddings records."""
        self.embedding_ids.unlink()

    @api.model
    def _cron_embed_records(self, batch_size: int = 100):
        """Cron job to create embedding records for existing un-embedded models.

        :param int batch_size: the size of the batch to process.
        """
        records_to_embed = []
        total_records_to_process = 0
        for model_name, Model in self.env.items():
            if (model_name != "ai.embedding.mixin" and isinstance(Model, AIEmbeddingMixin)):
                records = Model.search(Model._get_records_to_embed_domain())
                total_records_to_process += len(records)
                records_to_embed.append(records)

        if not records_to_embed:
            self.env["ir.cron"]._commit_progress(remaining=0)
            return

        processed = 0
        for records in records_to_embed:
            if processed >= batch_size:
                break
            for record in records[:batch_size - processed]:
                if record.embedding_status == "dirty":
                    record.embedding_ids.unlink()
                record._create_embedding_records(record._get_embedding_models())
                processed += 1

        self.env["ir.cron"]._commit_progress(processed, remaining=total_records_to_process - processed)

        # Trigger actual embedding computation
        self.env.ref("ai.ir_cron_generate_embedding")._trigger()

    @api.model
    def _get_records_to_embed_domain(self):
        """Returns a search domain for the records to embed

        :return: the domain of records to search for.
        :rtype: Domain
        """
        return (
            Domain("embedding_ids", "=", False)
            | Domain("embedding_status", "=", "dirty")
            | Domain.AND(
                [
                    Domain("embedding_ids.embedding_vector", "=", False),
                    Domain("embedding_ids.has_embedding_generation_failed", "=", False),
                ],
            )
        )

    def _create_embedding_records(self, embedding_models: set[str]):
        """Creates the embedding records for the recordset for each `embedding_models`

        :param set[str] embedding_models: set of models to create embedding records for
        :return: an `ai.embedding` recordset
        :rtype: AIEmbedding
        """
        already_embedded = {
            (res_id, model)
            for res_id, model in self.env["ai.embedding"]._read_group(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "in", self.ids),
                    ("embedding_model", "in", embedding_models),
                ],
                groupby=["res_id", "embedding_model"],
            )
        }
        needed = {
            record.id: {
                m for m in embedding_models if (record.id, m) not in already_embedded
            }
            for record in self
        }
        records_to_embed = self.filtered(lambda r: needed.get(r.id))
        if not records_to_embed:
            return self.env["ai.embedding"]

        embedding_vals = records_to_embed._get_duplicate_records(needed)
        for record in records_to_embed:
            for model in needed[record.id]:
                if (record.id, model) in embedding_vals:
                    continue
                try:
                    for chunk in record._get_embedding_chunks():
                        embedding_vals[record.id, model].append(
                            {
                                "embedding_model": model,
                                "res_model": record._name,
                                "res_id": record.id,
                                "content": chunk,
                            },
                        )
                except ValueError as e:
                    record._on_embedding_failure(e)
        return self.env["ai.embedding"].create(
            [item for vals in embedding_vals.values() for item in vals],
        )

    def _recreate_embeddings(self):
        """Re-creates the embedding records for the model. Used when embedded content changes,
        which requires re-chunking."""
        self.embedding_ids.unlink()

        for record in self:
            record._create_embedding_records(record._get_embedding_models())
        self.env.ref("ai.ir_cron_generate_embedding")._trigger()

    def _get_embedding_chunks(self):
        """Chunks the content of the record.

        :return: a list of chunks of the content of the record
        :rtype: list[str]
        """
        self.ensure_one()
        return chunk_text(self._get_embedding_content())

    def _get_duplicate_records(self, models_per_record: dict[int, set[str]]):
        """Retrieves records that have already been embedded.

        :param dict[int, set[str]] models_per_record: a dict containing a set of embedding models for each record id.
        :return: a dict of embedding vals, grouped by (record id, embedding_model).
        :rtype: dict[tuple[int, str], dict]
        """
        duplicates = defaultdict(list)
        for record in self:
            embedding_models = models_per_record.get(record.id)
            if not embedding_models:
                continue
            duplicate_record = self.env[self._name].search(
                [
                    record._get_duplicate_domain(),
                    ("embedding_ids.embedding_model", "in", embedding_models),
                ],
                limit=1,
            )
            if not duplicate_record:
                continue
            for emb in duplicate_record.embedding_ids.filtered(lambda e: e.embedding_model in embedding_models):
                duplicates[record.id, emb.embedding_model].append(
                    {
                        "res_id": record.id,
                        "res_model": record._name,
                        "content": emb.content,
                        "embedding_vector": emb.embedding_vector,
                        "embedding_model": emb.embedding_model,
                    },
                )
        return duplicates

    def _get_embedding_content(self):
        """Retrieves the content of record that should be embedded.

        :return: the content to embed
        :rtype: str
        :raises: ValueError if an error occurs during content processing
        """
        raise NotImplementedError(
            f"Model '{self._name}' must implement '_get_embedding_content'.",
        )

    def _get_embedding_models(self) -> set[str]:
        """Returns a set of embedding models for the current record.

        :return: a set of embedding models
        :rtype: set[str]
        """
        self.ensure_one()
        if agent := self.env.ref("ai.ai_default_agent", raise_if_not_found=False):
            return {agent.embedding_model}
        raise NotImplementedError(
            f"Model '{self._name}' must implement '_get_embedding_models'.",
        )

    def _get_duplicate_domain(self):
        """Returns the domain used to identify duplicate records.

        :return: the domain of duplicate records
        :rtype: Domain
        """
        self.ensure_one()
        return Domain("id", "=", self.id)

    def _on_embedding_failure(self, error):
        """Performs some operations when failing to create embedding records."""
        self.ensure_one()
        _logger.warning("Failed to embed %s(%s): %s", self._name, self.id, error)
