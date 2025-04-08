# Copyright (C) 2024 Konos
# Licensed under the GPL-3.0 License or later.

import logging
from urllib.parse import urljoin

import requests

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BASE_URL = "https://api.fintoc.com/v1/"
REQUEST_TIMEOUT = 15


class FintocAPIMixin(models.AbstractModel):
    _name = "fintoc.api.mixin"
    _description = "Utility Methods for Fintoc integration"

    def _send_request(self, endpoint, method, token, **kwargs):
        try:
            url = urljoin(BASE_URL, endpoint)
            headers = {"accept": "application/json", "Authorization": token}
            all_data = []
            while url:
                response = requests.request(
                    method, url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs
                )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)
                url = response.links.get("next", {}).get("url")
            return all_data
        except requests.exceptions.RequestException as error:
            _logger.exception("Fintoc API request failed: %s", error)
            raise UserError(_("Failed to connect to Fintoc API: %s") % error) from error
