# Copyright (C) 2024 Konos
# Licensed under the GPL-3.0 License or later.

{
    "name": "Buk Connector",
    "summary": """
        Streamlined connector for data synchronization with Odoo
    """,
    "author": "Konos",
    "website": "https://www.konos.cl",
    "category": "Accounting/Accounting",
    "version": "18.0.3.0.0",
    "depends": [
        "accountant",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rules.xml",
        "views/buk_connector_views.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "license": "LGPL-3",
}
