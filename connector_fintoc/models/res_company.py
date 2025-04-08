# Copyright (C) 2024 Konos
# Licensed under the GPL-3.0 License or later.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    fintoc_api_key = fields.Char(
        company_dependent=True, help="API Key used for request authentication"
    )
