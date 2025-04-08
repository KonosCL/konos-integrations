# Copyright (C) 2024 Konos
# Licensed under the GPL-3.0 License or later.

import logging
from datetime import datetime, timedelta

from dateutil.parser import parse

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)

DEFAULT_DAYS = 200


class AccountBankStatementLine(models.Model):
    _name = "account.bank.statement.line"
    _inherit = ["fintoc.api.mixin", "account.bank.statement.line"]

    fintoc_id = fields.Char(help="Movement identifier in Fintoc")

    def _find_partner(self, vat, partner, company_id):
        if not vat:
            return False
        vat = vat.upper()
        formatted_vat = ""
        if len(vat) == 9:
            formatted_vat = f"{vat[:8]}-{vat[8]}"
        elif len(vat) == 8:
            formatted_vat = f"{vat[:7]}-{vat[7]}"
        partner_id = self.env["res.partner"].search(
            [("vat", "=", formatted_vat), ("company_id", "in", [False, company_id.id])],
            limit=1,
        )
        if not partner_id:
            values = {
                "vat": formatted_vat,
                "name": partner or "",
            }
            partner_id = self.env["res.partner"].create(values)
        return partner_id.id

    def _create_statement_lines(self, values, company_id):
        bank_statement_line = self.env["account.bank.statement.line"]
        partner_id = self._find_partner(
            values.get("rut"), values.get("partner"), company_id
        )
        fintoc_id = bank_statement_line.search(
            [("fintoc_id", "=", values.get("fintoc_id"))]
        )
        if not fintoc_id:
            bank_statement_line.create(
                {
                    "fintoc_id": values.get("fintoc_id"),
                    "date": values.get("date"),
                    "ref": values.get("ref"),
                    "payment_ref": values.get("ref"),
                    "partner_id": partner_id,
                    "amount": values.get("amount"),
                    "currency_id": False,
                    "journal_id": values.get("journal_id"),
                    "statement_id": values.get("statement_id").id,
                }
            )
        return True

    def sync_bank_statements(self):
        _logger.info("Fetching bank movements from Fintoc")
        partner_bank_ids = self.env["res.partner.bank"].search(
            [("fintoc_id", "!=", False)]
        )
        for partner_bank_id in partner_bank_ids:
            # If we have an open Bank Statement we use it
            bank_statement = self.env["account.bank.statement"].search(
                [
                    ("name", "=", datetime.today().date()),
                    ("is_complete", "=", False),
                    ("journal_id", "=", partner_bank_id.journal_id.id),
                ],
                limit=1,
            )
            if not bank_statement:
                balance_start = (
                    self.env["account.bank.statement.line"]
                    .search(
                        [
                            ("date", "<=", datetime.today().date()),
                            ("journal_id", "=", partner_bank_id.journal_id.id),
                        ],
                        order="internal_index desc",
                        limit=1,
                    )
                    .running_balance
                    or 0
                )
                bank_statement = self.env["account.bank.statement"].create(
                    {
                        "name": datetime.today().date(),
                        "date": datetime.today().date(),
                        "balance_start": balance_start,
                    }
                )

            fintoc_days = partner_bank_id.fintoc_days or DEFAULT_DAYS
            date_until = datetime.today().date()
            date_from = (datetime.today() - timedelta(days=fintoc_days)).date()
            values = {}

            try:
                company_id = partner_bank_id.journal_id.company_id
                link_token = partner_bank_id.with_company(company_id).fintoc_token
                _logger.info("Company: %s", company_id.name)
                _logger.info("Account: %s", partner_bank_id.acc_number)
                _logger.info("Token: %s", link_token)
                fintoc_api_key = partner_bank_id.journal_id.company_id.fintoc_api_key
                fintoc_id = partner_bank_id.fintoc_id

                all_movements = self._send_request(
                    endpoint=f"accounts/{fintoc_id}/movements",
                    method="GET",
                    token=fintoc_api_key,
                    params={
                        "link_token": link_token,
                        "since": date_from,
                        "until": date_until,
                        "per_page": 100,
                    },
                )
                total_movements = len(all_movements)
                _logger.info("Retrieved %d movements", total_movements)
            except Exception as e:
                _logger.error(
                    "An error occurred synchronizing account movements: %s", e
                )
                raise UserError(
                    _(
                        "An error occurred synchronizing account movements. "
                        "Please check the logs for details."
                    )
                ) from e

            for i, movement in enumerate(all_movements, start=1):
                _logger.info("Processing movement %d/%d", i, total_movements)
                description = ""
                sender = ""
                rut = False
                try:
                    fintoc_id = movement["id"]
                    amount = movement["amount"] or "0"
                    if movement["currency"] in ["USD", "EUR"]:
                        amount = amount / 100
                    description = movement["description"] or ""
                    dt = parse(movement["post_date"])
                    formatted_date = dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                    post_date = Datetime.from_string(formatted_date)
                    currency_id = movement["currency"]
                    sender = ""
                    rut = False
                    if amount > 0:
                        if (
                            movement["sender_account"]
                            and movement["sender_account"]["holder_name"]
                        ):
                            sender = movement["sender_account"]["holder_name"]
                            rut = movement["sender_account"]["holder_id"]
                    else:
                        if (
                            movement["recipient_account"]
                            and movement["recipient_account"]["holder_name"]
                        ):
                            sender = movement["recipient_account"]["holder_name"] or ""
                            rut = movement["recipient_account"]["holder_id"] or False
                    values.update(
                        {
                            "date": post_date,
                            "ref": description,
                            "payment_ref": sender,
                            "partner": sender,
                            "fintoc_id": fintoc_id,
                            "amount": amount,
                            "currency_id": currency_id,
                            "narration": description,
                            "rut": rut,
                            "journal_id": partner_bank_id.journal_id.id,
                            "statement_id": bank_statement,
                        }
                    )
                    self._create_statement_lines(
                        values, partner_bank_id.journal_id.company_id
                    )
                except Exception as e:
                    _logger.error(f"An error occurred procesing movement: {e}")
                    raise UserError(
                        _(
                            "An error occurred procesing movement. "
                            "Please check the logs for details."
                        )
                    ) from e
            balance_end = bank_statement.balance_start + sum(
                bank_statement.line_ids.mapped("amount")
            )
            bank_statement.balance_end_real = balance_end or 0


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    @api.model
    def fix_initial_balances(self, date_from=None):
        # Set default date if `date_from` is not specified
        if not date_from:
            # Default date: October 10, 2024
            date_from = fields.Date.from_string("2024-10-10")
        else:
            date_from = fields.Date.from_string(date_from)

        _logger.info(
            "Iniciando la corrección de balances desde la fecha: %s", date_from
        )

        # Find the last statement prior to the `date_from` date
        previous_statement = self.search(
            [("date", "<", date_from)], order="date desc", limit=1
        )

        # Use the `balance_end_actual` from the last previous statement
        # as `previous_balance_end`
        previous_balance_end = (
            previous_statement.balance_end_real if previous_statement else 0.0
        )

        # Search for statements in the established date range that
        # are not completed
        statements = self.search(
            [("date", ">=", date_from)], order="first_line_index asc"
        )

        for statement in statements:
            # If the initial balance is different from the final balance of the
            # previous statement, adjust it
            if statement.balance_start != previous_balance_end:
                _logger.info(
                    "Corrigiendo balance inicial para el estado de cuenta: %s",
                    statement.name,
                )

                # Update the opening balance and recalculate
                statement.write({"balance_start": previous_balance_end})

                # Recalculate final balance using standard Odoo logic
                statement._compute_balance_end()

                # Get the new final balance after recalculation
                statement.balance_end_real = statement.balance_end

                _logger.info(
                    "Nuevo balance inicial ajustado para %s: %s",
                    statement.name,
                    statement.balance_start,
                )
                _logger.info(
                    "Nuevo balance final ajustado para %s: %s",
                    statement.name,
                    statement.balance_end_real,
                )

            # Update the previous final balance for the following statement
            previous_balance_end = statement.balance_end_real

    @api.model
    def _cron_fix_bank_statement_balances(self, date_from=None):
        # Pass `date_from` to `fix_initial_balances` function
        self.fix_initial_balances(date_from=date_from)
