# Copyright (C) 2024 Konos
# Licensed under the GPL-3.0 License or later.

import logging
from urllib.parse import urljoin

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


class BukInstance(models.Model):
    _name = "buk.instance"
    _inherit = ["mail.thread"]
    _description = "Buk Instance"

    name = fields.Char(help="Descriptive name to easily identify this Buk instance")
    token = fields.Char(help="This string is required to access Buk's API")
    base_url = fields.Char(tracking=True, help="Base URL of the Buk API")
    centralization_ep = fields.Char(
        string="Centralization",
        tracking=True,
        default="accounting",
        help="URL of the accounting centralization endpoint.",
    )
    ledger_account_ep = fields.Char(
        string="Ledger Account",
        tracking=True,
        default="ledger_account",
        help="URL of the ledger account endpoint",
    )
    cost_center_ep = fields.Char(
        string="Cost Center",
        tracking=True,
        default="centro_costo_definitions",
        help="URL of the cost center endpoint",
    )
    account_id = fields.Many2one(
        "account.account",
        tracking=True,
        help="This account will be used if no matching Buk account is found\n "
        "during the import process",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        tracking=True,
        help="This account will be used if no matching Buk cost center is\n "
        "found during the import process",
    )
    company_id = fields.Many2one(
        "res.company",
        tracking=True,
        default=lambda self: self.env.company,
        help="Company to which this Buk instance belongs. If not selected,\n "
        "the current user's company will be used",
    )
    buk_id = fields.Char(
        string="Buk ID",
        tracking=True,
        help="Unique ID assigned to the company in Buk. If empty, the,\n "
        "company's tax ID (RUT) will be used as the identifier",
    )

    def _send_request(self, endpoint, method, **kwargs):
        try:
            url = urljoin(self.base_url, endpoint)
            headers = {"auth_token": self.token}
            response = requests.request(
                method, url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            _logger.exception("Buk API request failed: %s", error)
            raise UserError(_("Failed to connect to Buk API: %s") % error) from error

    def _get_nested_value(self, data, nested_key, delimiter="."):
        if not isinstance(nested_key, str):
            raise UserError(f"Key must be a string, got {type(nested_key).__name__}")
        keys = nested_key.split(delimiter)
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None
        return data

    def _sync_data(self, endpoint, model_name, field_mapping):
        page = 1
        while True:
            try:
                response = self._send_request(endpoint, "GET", params={"page": page})
                data = response.get("data", [])
            except Exception as e:
                _logger.exception(f"Failed to sync data from {endpoint}: {e}")
                return False

            records = []
            _logger.info(f"Creating {model_name} mappings")
            for item in data:
                record_data = {
                    odoo_field: self._get_nested_value(item, buk_field)
                    for buk_field, odoo_field in field_mapping.items()
                }
                record_data["company_id"] = self.env.company.id
                record_data["instance_id"] = self.id
                records.append(record_data)

            if records:
                self.env[model_name].create(records)

            total_pages = response.get("pagination", {}).get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1
        return True

    def _sync_ledger_account(self):
        field_mapping = {
            "name": "name",
            "number": "code",
        }
        return self._sync_data(
            self.ledger_account_ep, "buk.account.mapping", field_mapping
        )

    def _sync_cost_center(self):
        field_mapping = {
            "custom_attributes.Definición": "name",
            "code": "code",
        }
        return self._sync_data(
            self.cost_center_ep, "buk.cost.center.mapping", field_mapping
        )

    def sync_master_data(self):
        account_ids = self.env["buk.account.mapping"].search_count(
            [("company_id", "=", self.company_id.id)]
        )
        cost_center_ids = self.env["buk.cost.center.mapping"].search_count(
            [("company_id", "=", self.company_id.id)]
        )
        if account_ids or cost_center_ids:
            raise UserError(_("Master data already imported"))
        self._sync_ledger_account()
        self._sync_cost_center()


class BukAccountMapping(models.Model):
    _name = "buk.account.mapping"
    _inherit = ["mail.thread"]
    _description = "Buk Accounting Account Mapping"

    name = fields.Char(
        help="Name of the Buk account. This is the account's identifier in Buk"
    )
    code = fields.Char(
        help="Code of the Buk account. This code is used to identify the\n "
        "account within Buk"
    )
    instance_id = fields.Many2one(
        "buk.instance",
        ondelete="restrict",
        help="Instance related to this Buk account equivalence",
    )
    account_id = fields.Many2one(
        "account.account",
        help="The equivalent account in Odoo. This is the Odoo account\n "
        "that corresponds to the Buk account",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        help="Company to which this Buk account equivalence belongs. If\n "
        "not selected, the current user's company will be used.",
    )


class BukCostCenterMapping(models.Model):
    _name = "buk.cost.center.mapping"
    _description = "Buk Cost Center Mapping"

    name = fields.Char(
        help="Name of the Buk cost center. This is the identifier used\n "
        "in Buk for the cost center"
    )
    code = fields.Char(
        help="Code of the Buk cost center. This code is used to uniquely\n "
        "identify the cost center within Buk"
    )
    instance_id = fields.Many2one(
        "buk.instance",
        ondelete="restrict",
        help="Instance related to this Buk cost center equivalence",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        help="The corresponding analytic account in Odoo. This is the Odoo\n "
        "account linked to the Buk cost center",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        help="Company to which this Buk cost center belongs. If not\n "
        "selected, the current user's company will be used",
    )


class BukAccountingPeriod(models.Model):
    _name = "buk.accounting.period"
    _inherit = ["mail.thread"]
    _description = "Buk Accounting Period"
    _order = "year desc, month desc"

    name = fields.Char(help="Name of the Buk period")
    state = fields.Selection(
        selection=[("draft", "Draft"), ("done", "Done")],
        string="Status",
        tracking=True,
        readonly=True,
        copy=False,
        default="draft",
    )
    month = fields.Char(help="Month for which the Buk period data is imported")
    year = fields.Char(help="Year for which the Buk period data is imported")
    journal_id = fields.Many2one(
        "account.journal", help="Journal where the entries will be generated"
    )
    account_move_id = fields.Many2one(
        "account.move",
        ondelete="restrict",
        tracking=True,
        help="Journal entry for this period. This links the Buk period\n "
        "to an Odoo accounting entry",
    )
    instance_id = fields.Many2one(
        "buk.instance", ondelete="restrict", help="Instance related to this Buk period"
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        help="Company to which this Buk period is related. This defines\n "
        "which company the period belongs to",
    )

    _sql_constraints = [
        (
            "unique_month_year_company",
            "UNIQUE(month, year, company_id)",
            "The combination of month and year must be unique per company.",
        )
    ]

    def _get_account(self, code):
        default_account_id = self.instance_id.account_id
        buk_account_id = self.env["buk.account.mapping"].search(
            [("code", "=", code)], limit=1
        )
        if buk_account_id and buk_account_id.account_id:
            default_account_id = buk_account_id.account_id
        return default_account_id.id

    def _get_analytic_account(self, code):
        default_analytic_id = self.instance_id.analytic_account_id
        buk_analytic_id = self.env["buk.cost.center.mapping"].search(
            [("code", "=", code)], limit=1
        )
        if buk_analytic_id and buk_analytic_id.analytic_account_id:
            default_analytic_id = buk_analytic_id.analytic_account_id
        return {default_analytic_id.id: 100.0}

    def _get_partner(self, vat):
        vat = vat.replace(".", "")
        default_partner_id = self.env.ref("base.main_partner")
        partner_id = self.env["res.partner"].search([("vat", "=", vat)], limit=1)
        if partner_id:
            default_partner_id = partner_id
        return default_partner_id.id

    def _prepare_move_values(self, data):
        move_line = {
            "account_id": self._get_account(data.get("account")),
            "partner_id": self._get_partner(data.get("employee_rut")),
            "analytic_distribution": self._get_analytic_account(
                data.get("cost_center")
            ),
            "name": data.get("description"),
            "debit": (data["amount"] if data["entry_type"] == "debit" else 0.0),
            "credit": (data["amount"] if data["entry_type"] == "credit" else 0.0),
        }
        return move_line

    def _sync_accounting_period(self):
        params = {
            "month": self.month,
            "year": self.year,
            "company_id": self.instance_id.buk_id
            or self.company_id.vat.replace("-", ""),
            "page": 1,
        }
        content = self.instance_id._send_request(
            self.instance_id.centralization_ep, "GET", params=params
        )
        pages = content["pagination"]["total_pages"]
        data = []
        # REVIEW: too much for loops here! This should be improved.
        for page in range(1, pages + 1):
            params["page"] = page
            content = self.instance_id._send_request(
                self.instance_id.centralization_ep, "GET", params=params
            )
            data.extend(content["data"])

        move_lines = []
        values = {
            "journal_id": self.journal_id.id,
            "line_ids": move_lines,
        }

        for group in data:
            if group["items"]:
                for line in group["items"]:
                    move_line = self._prepare_move_values(line)
                    move_lines.extend([(0, 0, move_line)])
            values.update(
                {
                    "line_ids": move_lines,
                }
            )

        try:
            account_move_id = (
                self.env["account.move"]
                .with_context(check_move_validity=False)
                .create(values)
            )
        except Exception as error:
            _logger.error(error)
            raise UserError(_("Cannot create account movement.")) from error

        self.write({"account_move_id": account_move_id.id, "state": "done"})
        return True

    def import_period(self):
        self._sync_accounting_period()
