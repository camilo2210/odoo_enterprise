FROM odoo:20.0

USER root

# gcc y python3-dev ya vienen incluidos en la imagen base de Odoo.
# Solo instala lo que realmente falta:
RUN pip3 install --no-cache-dir \
    paramiko \
    pgvector

USER odoo
