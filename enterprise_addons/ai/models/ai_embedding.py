# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from collections import defaultdict

from requests.exceptions import RequestException

from odoo import api, fields, models, modules
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools import SQL

from odoo.addons.ai.orm.field_vector import Vector
from odoo.addons.ai.utils.ai_utils import call_odoo_ai
from odoo.addons.iap import InsufficientCreditError

MAX_BATCH_SIZE = 100
MAX_TOKENS = 10000

_logger = logging.getLogger(__name__)


class AIEmbedding(models.Model):
    _name = 'ai.embedding'
    _description = "Attachment Chunks Embedding"
    _explanation = "Stores vector embeddings for document chunks. Used to perform semantic searches to find relevant context for user queries."
    _order = 'sequence'

    res_id = fields.Many2oneReference(
        string="The ID of a linked record.",
        model_field="res_model",
        required=True,
        index=True,
    )
    res_model = fields.Char(string="The model of a linked record", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    content = fields.Text(string="Chunk Content", required=True)
    embedding_model = fields.Char(string="Embedding Model")
    has_embedding_generation_failed = fields.Boolean(string="Has Embedding Generation Failed", default=False)
    embedding_error = fields.Char(string="Embedding error")
    embedding_vector = Vector(size=1536)
    _embedding_vector_idx = models.Index("USING hnsw (embedding_vector vector_cosine_ops)")

    @api.model
    def _get_similar_chunks(self, query_embedding, target_per_model, embedding_model, top_n=5):
        if not target_per_model:
            return None
        target_filter = SQL(" OR ").join(
            SQL("(res_model = %s AND res_id IN %s)", model, tuple(target.ids))
            for model, target in target_per_model.items()
        )
        return self.browse(
            id_
            for id_, *_ in self.env.execute_query(
                SQL(
                    """
                    SELECT
                        id,
                        1 - (embedding_vector <=> %s::vector) AS similarity
                    FROM ai_embedding
                    WHERE embedding_vector IS NOT NULL
                    AND embedding_model = %s
                    AND %s
                    ORDER BY similarity DESC
                    LIMIT %s;
                """,
                    query_embedding,
                    embedding_model,
                    target_filter,
                    top_n,
                ),
            )
        )

    @api.model
    def _get_similar_documents(self, query_model, target_models, embedding_model: str, max_distance: float | None = None, limit: int = 100):
        if not query_model or not target_models:
            return self.env[query_model._name]

        return self.env[query_model._name].browse(
            id_
            for id_, *_ in self.env.execute_query(
                SQL(
                    """
                    WITH min_per_chunk AS (
                        SELECT q.id as query_chunk, q.res_id as query_id, d.res_id as document_id, MIN(q.embedding_vector <=> d.embedding_vector) AS distance
                        FROM ai_embedding q
                        JOIN ai_embedding d on d.res_model = q.res_model AND d.res_id != q.res_id AND d.embedding_model = q.embedding_model
                        WHERE q.res_id = %s AND q.res_model = %s AND q.embedding_model = %s AND d.res_id in %s
                        GROUP BY q.id, d.res_id
                        ORDER BY d.res_id
                    ), similar_documents AS (
                        SELECT document_id, AVG(distance) AS avg_distance
                        FROM min_per_chunk
                        GROUP BY document_id
                        HAVING AVG(distance) < %s
                    )
                    SELECT r.id
                    FROM %s r
                    JOIN similar_documents s ON s.document_id = r.id
                    ORDER BY s.avg_distance ASC
                    LIMIT %s;
                """,
                    query_model.id,
                    query_model._name,
                    embedding_model,
                    tuple(target_models.ids),
                    max_distance,
                    SQL.identifier(self.env[query_model._name]._table),
                    limit,
                ),
            )
        )

    @api.model
    def _cron_generate_embedding(self, batch_size=100):
        """
        Generate embedding vectors for content.
        """
        # Check for all the embedding vectors to be generated
        missing_embeddings = self.search([
            ("embedding_vector", "=", False),
            ("has_embedding_generation_failed", "=", False),
            ("embedding_model", "!=", False),
        ])

        if not missing_embeddings:
            self.env["ir.cron"]._commit_progress(remaining=0)
            return None

        self._generate_embeddings(missing_embeddings[:batch_size])

        if len(missing_embeddings) > batch_size:
            # we still have unfinished embeddings to generate: run the CRON again
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()
            return True

        return False

    def _generate_embeddings(self, missing_embedding_records):
        """Generate vectors for a batch of embedding records, grouped by model."""
        embeddings_by_model = defaultdict(list)
        for embedding in missing_embedding_records:
            embeddings_by_model[embedding.embedding_model].append(embedding)

        _logger.info("Starting embedding update - missing %s embeddings.", len(missing_embedding_records))
        self.env['ir.cron']._commit_progress(remaining=len(missing_embedding_records))
        failed_embeddings = self.env[self._name]
        iap_credit_error_embeddings = self.env[self._name]

        # Process each model group separately
        for model, embeddings in embeddings_by_model.items():
            batches = self._create_batches(embeddings)
            _logger.info(
                "Processing %s embeddings in %s batches",
                len(embeddings), len(batches),
            )

            for batch_idx, batch in enumerate(batches):
                try:
                    _logger.info(
                        "Processing batch %s/%s with %s embeddings",
                        batch_idx + 1, len(batches), len(batch),
                    )

                    embedding_titles = {}
                    ids_per_model = defaultdict(set)
                    for idx, emb in enumerate(batch):
                        ids_per_model[emb.res_model].add(emb.res_id)

                    for res_model, res_ids in ids_per_model.items():
                        if res_model not in self.env:
                            continue
                        records = (
                            self.env[res_model]
                            .with_context(active_test=False)
                            .search([("id", "in", res_ids)])
                        )
                        embedding_titles |= {(res_model, record.id): record.display_name for record in records}

                    # Get embeddings for the entire batch
                    response = self._get_embeddings(
                        input=[{'title': embedding_titles.get((emb.res_model, emb.res_id)), 'content': emb.content} for emb in batch],
                        model=model,
                        mode="document",
                    )
                    vectors = response['embeddings']

                    # Update each embedding record with its corresponding vector
                    for idx, embedding in enumerate(batch):
                        try:
                            embedding.embedding_vector = vectors[idx]
                        except KeyError as e:
                            _logger.error(
                                "Failed to extract embedding for record %s: %s",
                                embedding.id, e,
                            )
                            failed_embeddings |= embedding

                    # Commit progress for this batch
                    if not self.env['ir.cron']._commit_progress(len(batch)):
                        break

                except (RedirectWarning, RequestException, UserError, AttributeError) as e:
                    _logger.error(
                        "Failed to process batch %s/%s: %s",
                        batch_idx + 1, len(batches), e,
                    )
                    # Mark all embeddings in failed batch as failed
                    failed_embeddings |= batch
                except InsufficientCreditError:
                    for remaining_batch in batches[batch_idx:]:
                        iap_credit_error_embeddings |= remaining_batch
                    break  # The next requests will also fail with an IAP credit error, so it can be skipped

        all_failed_embeddings = failed_embeddings | iap_credit_error_embeddings
        if all_failed_embeddings:
            all_failed_embeddings.has_embedding_generation_failed = True
            if iap_credit_error_embeddings:
                iap_credit_error_embeddings.embedding_error = "iap_credit_error"
            self.env["ir.cron"]._commit_progress(len(all_failed_embeddings))

    @api.ormcache()
    def _get_default_embedding_model(self):
        if modules.module.current_test:
            return 'dummy'
        return call_odoo_ai(self.env, "1/get_default_embedding_model", {}, add_iap_token=False)

    @api.ormcache()
    def _get_supported_embedding_models(self):
        if modules.module.current_test:
            return 'dummy'
        return call_odoo_ai(self.env, "1/get_supported_embedding_models", {}, add_iap_token=False)

    def _estimate_tokens(self, text):
        """Estimate token count based on text length.
        Based on https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
        :param text: Text to estimate tokens for
        :type text: str
        :return: Estimated token count
        :rtype: int
        """
        return len(text) // 4 if text else 0

    def _create_batches(self, embeddings):
        """
        Group embeddings into batches
        :param embeddings: List of embeddings to group into batches
        :type embeddings: list[AIEmbedding]
        :return: List of batches
        :rtype: list[list[AIEmbedding]]
        """

        batches = []
        current_batch = self.env[self._name]
        current_batch_tokens = 0

        for embedding in embeddings:
            content_tokens = self._estimate_tokens(embedding.content)
            if (len(current_batch) >= MAX_BATCH_SIZE) or \
                (current_batch_tokens + content_tokens > MAX_TOKENS):
                batches.append(current_batch)
                current_batch = self.env[self._name]
                current_batch_tokens = 0

            current_batch |= embedding
            current_batch_tokens += content_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    @api.model
    def _get_embeddings(self, input, model, mode):
        params = {
            'input': input,
            'model': model,
            'mode': mode,
        }
        return call_odoo_ai(self.env, "1/get_embeddings", params)

    def _cron_update_deprecated_embedding_models(self, batch_size: int = 100_000):
        supported_embedding_models = self._get_supported_embedding_models()

        deprecated_domain = [('embedding_model', 'not in', supported_embedding_models)]
        embeddings_to_update_count = self.env["ai.embedding"].search_count(deprecated_domain)
        embeddings_to_update = self.env["ai.embedding"].search(
            deprecated_domain, limit=batch_size,
        )
        self.env['ir.cron']._commit_progress(remaining=embeddings_to_update_count)

        default_embedding_model = self._get_default_embedding_model()
        embeddings_to_update.write({
            "embedding_model": default_embedding_model,
            "embedding_vector": None,
            "has_embedding_generation_failed": False,
            "embedding_error": False,
        })

        agents_to_update = self.env['ai.agent'].search([('embedding_model', 'not in', supported_embedding_models)])
        agents_to_update.embedding_model = default_embedding_model

        self.env.ref('ai.ir_cron_generate_embedding')._trigger()
        self.env["ir.cron"]._commit_progress(len(embeddings_to_update))
