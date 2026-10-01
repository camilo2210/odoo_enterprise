# Part of Odoo. See LICENSE file for full copyright and licensing details
import html
import logging
import re
import traceback
from datetime import datetime
from itertools import batched, islice

from psycopg2.errors import SerializationFailure

from odoo import fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.json import scriptsafe as json_safe

BLOGS_BATCH_SIZE = 50
TAGS_BATCH_SIZE = 50
BLOG_POSTS_BATCH_SIZE = 50
MAX_BLOG_FAIL_REPORT = 10
UNCROPPED_IMAGES_BATCH_SIZE = 10

logger = logging.getLogger(__name__)


class Website_GeneratorRequest(models.Model):
    _inherit = 'website_generator.request'
    import_blogs = fields.Boolean("Import Blogs", default=False)
    blog_platform = fields.Char(string="Blog Platform of the website", default='wordpress')

    def _get_call_params(self):
        data = super()._get_call_params()
        data['import_blogs'] = self.import_blogs
        data['blog_platform'] = self.blog_platform
        return data

    def _generation_progress_init(self):
        generation_progress = super()._generation_progress_init()
        generation_progress.update({
            'blog_id_mapping': {},
            'tag_id_mapping': {},
            'last_blog_id': 0,
            'failed_last_blog_id': 0,
            'failed_blogs': [],
            'last_blog_tag_id': 0,
            'failed_last_blog_tag_id': 0,
            'failed_blog_tags': [],
            'last_blog_post_id': 0,
            'failed_last_blog_post_id': 0,
            'failed_blog_posts': [],
            'created_blog_post_ids': [],
            'last_blog_post_fixup_id': 0,
            'failed_last_blog_post_fixup_id': 0,
            'failed_blog_post_fixups': [],
            'n_report_iap_blogs': 0,
            'last_uncropped_blog_image_id': 0,
        })
        return generation_progress

    def _report_blog_fail(self):
        generation_progress = self.generation_progress
        if generation_progress['n_report_iap_blogs'] >= MAX_BLOG_FAIL_REPORT:
            logger.warning('Too many blog failures, stop reporting to IAP')
            return

        self._report_to_iap('report_ko', partial_error=True, error=traceback.format_exc())
        generation_progress['n_report_iap_blogs'] += 1
        self.generation_progress = generation_progress
        self.env.cr.commit()

    def batch_create_records(self, generation_progress, blog_entity_vals, entity_type, last_record_id, batch_size, request_index, total_requests, create_record_fn, **kwargs):
        # A wrapper function for creating the blog.blog, blog.post and blog.tag records
        last_blog_id = generation_progress[last_record_id]
        for batch_blog_data in batched(islice(blog_entity_vals, last_blog_id, None), batch_size):
            try:
                generation_progress = create_record_fn(generation_progress, batch_blog_data, **kwargs)

                # Save progress
                generation_progress[last_record_id] = min(len(blog_entity_vals), generation_progress[last_record_id] + batch_size)
                self.generation_progress = generation_progress
                if 'failed' not in last_record_id:
                    msg = "Request %s/%s, Importing %s: %s/%s"
                else:
                    msg = "Request %s/%s, Retrying %s: %s/%s"
                logger.info(msg, request_index + 1, total_requests, entity_type, generation_progress[last_record_id], len(blog_entity_vals))
                self.env['ir.cron']._commit_progress(processed=1, remaining=1)
            except SerializationFailure:
                # Here to re-trigger the cron in case of SerializationFailure
                raise
            except Exception:
                self.env['ir.cron']._rollback_progress()
                if 'failed' not in last_record_id:
                    msg = f"Error importing batched {entity_type}. Will retry."
                else:
                    msg = f"Error retrying batched {entity_type}. Ignoring..."
                logger.exception(msg)
                self._report_blog_fail()
                if batch_size != 1 and 'failed' not in last_record_id:
                    generation_progress['failed_' + entity_type] += list(range(generation_progress[last_record_id], generation_progress[last_record_id] + len(batch_blog_data)))
                    self.generation_progress = generation_progress
                    self.env['ir.cron']._commit_progress(processed=1, remaining=1)
                generation_progress[last_record_id] = min(len(blog_entity_vals), generation_progress[last_record_id] + batch_size)

    def _create_blog_blogs(self, generation_progress, batch_blog_data):
        blog_names = [blog.get('name', '') for _, blog in batch_blog_data]
        # Check if the blog already exists for the website.
        # This could occur when the user already started manually adding blogs but wanted the tool to do the rest.
        already_existing_blogs = self.env['blog.blog'].search([('name', 'in', blog_names), ('website_id', '=', self.website_id.id)])
        batched_blog_names = {existing_blog.name for existing_blog in already_existing_blogs}

        batched_blog_vals = []
        # Used for linking the created odoo record to the corresponding blog info in batch_blog_data
        blog_name_mapping = {}
        for blog_path, blog in batch_blog_data:
            blog_name = blog.get('name', '')
            blog_name_mapping[blog_name] = {
                'id': blog['id'],
                'path': blog_path,
            }
            if blog_name in batched_blog_names:
                continue
            batched_blog_names.add(blog_name)

            batched_blog_vals.append({
                'name': blog_name,
                'subtitle': blog.get('description', ''),
                'website_id': self.website_id.id,
            })
        odoo_blogs = already_existing_blogs + self.env['blog.blog'].sudo().create(batched_blog_vals)
        for odoo_blog in odoo_blogs:
            blog_path = blog_name_mapping[odoo_blog.name]['path']
            generation_progress['direct_html_replacements_mapping'][blog_path] = odoo_blog.website_url
            blog_id = blog_name_mapping[odoo_blog.name]['id']
            generation_progress['blog_id_mapping'][blog_id] = odoo_blog.id

        return generation_progress

    def _create_blog_tags(self, generation_progress, batch_blog_tag_data):
        blog_tag_names = [blog_tag.get('name', '') for _, blog_tag in batch_blog_tag_data]
        # Blog tags have a uniqueness constraint
        already_existing_blog_tags = self.env['blog.tag'].search([('name', 'in', blog_tag_names)])
        batched_blog_tag_names = {existing_blog_tag.name for existing_blog_tag in already_existing_blog_tags}

        batched_blog_tag_vals = []
        batched_blog_tag_id_mapping = {}
        blog_tag_name_mapping = {}
        for blog_tag_path, blog_tag in batch_blog_tag_data:
            blog_tag_name = blog_tag.get('name', '')
            batched_blog_tag_id_mapping[blog_tag_name] = blog_tag['id']
            blog_tag_name_mapping[blog_tag_name] = blog_tag_path
            if blog_tag_name in batched_blog_tag_names:
                continue
            batched_blog_tag_names.add(blog_tag_name)

            batched_blog_tag_vals.append({
                'name': blog_tag_name,
            })

        odoo_blog_tags = already_existing_blog_tags + self.env['blog.tag'].sudo().create(batched_blog_tag_vals)
        # Make the mapping of the external blog id to the odoo blog id so that it is applied to the correct blog posts.
        for odoo_blog_tag in odoo_blog_tags:
            blog_tag_id = batched_blog_tag_id_mapping[odoo_blog_tag.name]
            generation_progress['tag_id_mapping'][blog_tag_id] = odoo_blog_tag.id
            tag_url = self.env['ir.http']._slug(odoo_blog_tag)
            tag_url = f'/blog/tag/{tag_url}'
            blog_tag_path = blog_tag_name_mapping[odoo_blog_tag.name]
            generation_progress['direct_html_replacements_mapping'][blog_tag_path] = tag_url

        return generation_progress

    def _create_blog_posts(self, generation_progress, batch_blog_post_data, pattern_sorted_html, direct_html_replacements_mapping, all_blog_images):
        batched_blog_post_vals = []
        blog_name_path_mapping = {}
        for i, (blog_post_path, blog_post) in enumerate(batch_blog_post_data):
            blog_post_name = blog_post.get('name')
            blog_post_vals = {
                'name': blog_post_name,
                'teaser_manual': blog_post.get('teaser_manual'),
                'content': blog_post.get('content'),
                'is_published': blog_post.get('is_published'),
            }
            blog_name_path_mapping[blog_post_name] = blog_post_path

            # In WordPress, blog posts can belong to multiple blogs.
            # However, this is not the case in Odoo.
            # So we take the most common blog as the blog of the blog post. This choice is done WS side.
            valid_blog_id = blog_post.get('blog_id')
            if (not valid_blog_id and valid_blog_id != 0) or valid_blog_id not in generation_progress['blog_id_mapping']:
                # If somehow we didn't manage to create the blog id, then we simply take the first one as a backup from the list of ids
                blog_ids = blog_post.get('blog_ids', [])

                for blog_id in blog_ids:
                    if blog_id in generation_progress['blog_id_mapping']:
                        valid_blog_id = blog_id
                        break

            image_replacement_mapping = self._save_customized_images_as_attachments(blog_post, generation_progress)
            blog_post_vals['content'] = self._apply_html_replacements([blog_post.get('content', '')], pattern_sorted_html, direct_html_replacements_mapping, image_replacement_mapping)[0]

            # Odoo only allows for a blog post to be associated with 1 blog
            # If not blog id, it will default to the base blog.
            if valid_blog_id:
                blog_post_vals['blog_id'] = generation_progress['blog_id_mapping'][valid_blog_id]

            tag_ids = []
            for tag_id in blog_post.get('tag_ids', []):
                # Account for the case that the tag id could not be created.
                odoo_tag_id = generation_progress['tag_id_mapping'].get(tag_id)
                if odoo_tag_id:
                    tag_ids.append(odoo_tag_id)

            if tag_ids:
                blog_post_vals['tag_ids'] = tag_ids

            published_date_str = blog_post.get('published_date')
            if published_date_str:
                blog_post_vals['published_date'] = datetime.strptime(published_date_str, DEFAULT_SERVER_DATETIME_FORMAT)

            img_name = all_blog_images.get(blog_post.get('image'))
            img_att_mapping = self._get_wg_attachment([img_name], generation_progress, reuse=False)
            img_att = img_att_mapping.get(img_name)

            if img_att:
                blog_post_vals.update({
                    'cover_properties': json_safe.dumps({
                        'background-image': f'url("{img_att.image_src}")',
                        'resize_class': 'o_half_screen_height',
                    }),
                })

            batched_blog_post_vals.append(blog_post_vals)

        odoo_blog_posts = self.env['blog.post'].sudo().create(batched_blog_post_vals)

        for odoo_blog_post in odoo_blog_posts:
            blog_path = blog_name_path_mapping[odoo_blog_post.name]
            generation_progress['direct_html_replacements_mapping'][blog_path] = odoo_blog_post.website_url
        generation_progress['created_blog_post_ids'].extend(odoo_blog_posts.ids)
        return generation_progress

    def _fixup_blog_post_links(self, generation_progress, batch_post_ids, full_pattern, full_mapping):
        # Applied after all blog posts exist, so that posts referencing each other get the correct links.
        posts = self.env['blog.post'].sudo().browse(batch_post_ids)
        for post in posts:
            new_content = self._apply_html_replacements([post.content], full_pattern, full_mapping, {})[0]
            if new_content != post.content:
                post.content = new_content
        return generation_progress

    def _create_blogs(self, request_index, total_requests, odoo_blocks, generation_progress):
        if not self.import_blogs:
            return 0

        all_blog_images = odoo_blocks['website'].get('all_blog_images', {})
        blogs = odoo_blocks.get("blogs", {})
        blog_posts = odoo_blocks.get("blog_posts", {})
        blog_tags = odoo_blocks.get("blog_tags", {})

        last_uncropped_image_id = generation_progress['last_uncropped_blog_image_id']

        for uncropped_images_batch in batched(islice(all_blog_images.items(), last_uncropped_image_id, None), UNCROPPED_IMAGES_BATCH_SIZE):
            uncropped_images_filenames = [img_name for img_url, img_name in uncropped_images_batch]
            attachments_map = self._get_wg_attachment(uncropped_images_filenames, generation_progress, reuse=True)
            for img_url, img_name in uncropped_images_batch:
                attachment = attachments_map.get(img_name)
                if not attachment:
                    continue

                generation_progress['image_url_to_filename'][img_url] = img_name
                generation_progress['direct_html_replacements_mapping'][html.escape(img_url)] = attachment.image_src

            generation_progress['last_uncropped_blog_image_id'] = min(len(all_blog_images), generation_progress['last_uncropped_blog_image_id'] + UNCROPPED_IMAGES_BATCH_SIZE)
            logger.info("Importing blog images: %s/%s", generation_progress['last_uncropped_blog_image_id'], len(all_blog_images))
            self.generation_progress = generation_progress
            # Commit progress only looks if process was done and if there is some remaining
            # Since the remaining is hard to know depending on the context and a bit meaningless, we avoid doing complex computation
            # We just set these values to say that there was progress and that their is still work to do
            self.env['ir.cron']._commit_progress(processed=1, remaining=1)

        # Set the title above cover view as it is cleaner
        title_above_cover_view = self.env['ir.ui.view'].with_context(active_test=False).search([('key', '=', 'website_blog.opt_blog_post_regular_cover')], limit=1)
        if title_above_cover_view and not title_above_cover_view.active:
            title_above_cover_view.write({'active': True})

        ## We need to create the blog.blog, blog.post and blog.tag
        # Create the blogs
        blogs_list = list(blogs.items())
        self.batch_create_records(generation_progress, blogs_list, 'blogs', 'last_blog_id', BLOGS_BATCH_SIZE, request_index, total_requests, self._create_blog_blogs)

        retry_blogs = [blogs_list[i] for i in generation_progress['failed_blogs']]
        self.batch_create_records(generation_progress, retry_blogs, 'blogs', 'failed_last_blog_id', 1, request_index, total_requests, self._create_blog_blogs)

        # Create the blog tags
        blog_tags_list = list(blog_tags.items())
        self.batch_create_records(generation_progress, blog_tags_list, 'blog_tags', 'last_blog_tag_id', TAGS_BATCH_SIZE, request_index, total_requests, self._create_blog_tags)

        retry_tags = [blog_tags_list[i] for i in generation_progress['failed_blog_tags']]
        self.batch_create_records(generation_progress, retry_tags, 'blog_tags', 'failed_last_blog_tag_id', 1, request_index, total_requests, self._create_blog_tags)

        # Load direct replacements
        direct_html_replacements_mapping = generation_progress['direct_html_replacements_mapping']
        sorted_original_html = sorted(direct_html_replacements_mapping.keys(), key=len, reverse=True)
        pattern_sorted_html = r'(' + '|'.join(map(re.escape, sorted_original_html)) + r')'

        blog_posts_lists = list(blog_posts.items())
        self.batch_create_records(
            generation_progress, blog_posts_lists, 'blog_posts', 'last_blog_post_id', BLOG_POSTS_BATCH_SIZE,
            request_index, total_requests, self._create_blog_posts, pattern_sorted_html=pattern_sorted_html,
            direct_html_replacements_mapping=direct_html_replacements_mapping, all_blog_images=all_blog_images,
        )

        retry_blog_posts = [blog_posts_lists[i] for i in generation_progress['failed_blog_posts']]
        self.batch_create_records(
            generation_progress, retry_blog_posts, 'blog_posts', 'failed_last_blog_post_id', 1,
            request_index, total_requests, self._create_blog_posts, pattern_sorted_html=pattern_sorted_html,
            direct_html_replacements_mapping=direct_html_replacements_mapping, all_blog_images=all_blog_images,
        )

        # Now that we have all the blogs created, we have to do the direct html replacement here
        # So that blogs that reference each other will have the correct links.
        created_blog_post_ids = generation_progress.get('created_blog_post_ids', [])
        if created_blog_post_ids:
            full_mapping = generation_progress['direct_html_replacements_mapping']
            full_sorted = sorted(full_mapping.keys(), key=len, reverse=True)
            full_pattern = r'(' + '|'.join(map(re.escape, full_sorted)) + r')'

            self.batch_create_records(
                generation_progress, created_blog_post_ids, 'blog_post_fixups', 'last_blog_post_fixup_id', BLOG_POSTS_BATCH_SIZE,
                request_index, total_requests, self._fixup_blog_post_links,
                full_pattern=full_pattern, full_mapping=full_mapping,
            )

            retry_fixups = [created_blog_post_ids[i] for i in generation_progress['failed_blog_post_fixups']]
            self.batch_create_records(
                generation_progress, retry_fixups, 'blog_post_fixups', 'failed_last_blog_post_fixup_id', 1,
                request_index, total_requests, self._fixup_blog_post_links,
                full_pattern=full_pattern, full_mapping=full_mapping,
            )

        return len(blog_posts)
