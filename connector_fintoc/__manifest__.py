# Copyright (C) 2024 Konos
# Licensed under the GPL-3.0 License or later.

{
    "name": "Fintoc Connector",
    "summary": """
        Retrieve bank statements directly from Fintoc into Odoo
    """,
    "author": "Konos",
    "website": "https://www.konos.cl",
    "category": "Accounting/Accounting",
    "version": "18.0.4.0.0",
    "depends": [
        "account_accountant",
    ],
    "data": [
        "data/ir_cron.xml",
        "views/account_bank_statement.xml",
        "views/res_bank_view.xml",
        "views/res_company.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "license": "LGPL-3",
}
