# Copyright (C) 2024 Konos
# Licensed under the GPL-3.0 License or later.

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartnerBank(models.Model):
    _name = "res.partner.bank"
    _inherit = ["fintoc.api.mixin", "res.partner.bank"]

    fintoc_id = fields.Char(
        string="Fintoc Account ID",
        help="Identifier associated with this account in Fintoc",
    )
    fintoc_token = fields.Char(help="Token associated with this account in Fintoc")
    fintoc_days = fields.Integer(
        string="Days Lookup", default=30, help="Day limit to search for movements"
    )

    def get_fintoc_account_id(self):
        _logger.info("Fetching Fintoc account ID for %s", self.acc_number)
        restrictions = {
            _(
                "There is no Fintoc API key for this company."
            ): not self.journal_id.company_id.fintoc_api_key,
            _("There is no Fintoc token for this account."): not self.fintoc_token,
            _("The account already has a Fintoc ID assigned."): self.fintoc_id,
        }
        messages = [key for key, value in restrictions.items() if value]
        if messages:
            raise UserError(
                _("Cannot continue due to the following restrictions: " "\n\t%s")
                % ("\n\t".join(messages))
            )

        accounts = self._send_request(
            endpoint="accounts",
            method="GET",
            token=self.journal_id.company_id.fintoc_api_key,
            params={"link_token": self.fintoc_token},
        )
        fintoc_id = next(
            (
                account.get("id")
                for account in accounts
                if account.get("number") == self.acc_number
            ),
            None,
        )
        if not fintoc_id:
            raise UserError(_("No matching account found in Fintoc."))
        self.fintoc_id = fintoc_id
