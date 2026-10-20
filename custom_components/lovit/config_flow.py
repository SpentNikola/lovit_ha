"""Config and options flow for the Lovit integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, override

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_LOGIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .lovit_api import (
    LovitAccountData,
    LovitAuthError,
    LovitClient,
    LovitConnectionError,
    LovitError,
)
from .schema import Required, Schema

_USER_SCHEMA = Schema(
    {
        Required(CONF_LOGIN): str,
        Required(CONF_PASSWORD): str,
    }
)

_SCAN_INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_SCAN_INTERVAL,
        max=MAX_SCAN_INTERVAL,
        step=1,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement="min",
    )
)


async def _async_validate_credentials(
    hass: HomeAssistant, login: str, password: str
) -> LovitAccountData:
    """Sign in to lk.lovit.ru once to validate the credentials."""
    session = async_create_clientsession(hass)
    client = LovitClient(session, login, password)
    try:
        return await client.async_login()
    finally:
        await client.async_close()


class LovitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Lovit config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the personal cabinet credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            login = user_input[CONF_LOGIN].strip()
            password = user_input[CONF_PASSWORD]
            try:
                data = await _async_validate_credentials(self.hass, login, password)
            except LovitAuthError:
                errors["base"] = "invalid_auth"
            except LovitConnectionError:
                errors["base"] = "cannot_connect"
            except LovitError:
                errors["base"] = "unknown"
            except Exception:  # noqa: BLE001 - never leak a traceback into the UI
                LOGGER.exception("Unexpected error while validating Lovit credentials")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(login.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Lovit {data.login or login}",
                    data={CONF_LOGIN: login, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_USER_SCHEMA, user_input),
            errors=errors,
        )

    @override
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start the re-authentication flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password after the stored one stopped working."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        login: str = entry.data[CONF_LOGIN]

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                await _async_validate_credentials(self.hass, login, password)
            except LovitAuthError:
                errors["base"] = "invalid_auth"
            except LovitConnectionError:
                errors["base"] = "cannot_connect"
            except LovitError:
                errors["base"] = "unknown"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error while re-authenticating")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: password},
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=Schema({Required(CONF_PASSWORD): str}),
            description_placeholders={"login": login},
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> LovitOptionsFlow:
        """Return the options flow for the integration."""
        return LovitOptionsFlow()


class LovitOptionsFlow(OptionsFlow):
    """Allow changing the polling interval."""

    @override
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options of a Lovit config entry."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=Schema(
                {Required(CONF_SCAN_INTERVAL, default=current): _SCAN_INTERVAL_SELECTOR}
            ),
        )
