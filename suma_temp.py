import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from dotenv import load_dotenv
from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

DOTENV_PATH = Path(__file__).resolve().with_name(".env")


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y"}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _log_info(debug: bool, message: str) -> None:
    if debug:
        print(f"[INFO] {message}")


def _log_step(step: str) -> None:
    print(f"[DONE] {step}")


def _wait_for_network_idle(page: Page, timeout_ms: int = 10000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass


def _click_first_visible(
    locators: Sequence[Locator],
    description: str,
    timeout_ms: int = 5000,
) -> None:
    last_error: Optional[Exception] = None
    for locator in locators:
        try:
            locator.first.wait_for(state="visible", timeout=timeout_ms)
            locator.first.click(timeout=timeout_ms)
            return
        except PlaywrightTimeoutError as error:
            last_error = error
            continue
    raise RuntimeError(f"Could not click {description}.") from last_error


def _fill_first_visible(
    locators: Sequence[Locator],
    value: str,
    description: str,
    timeout_ms: int = 5000,
) -> None:
    last_error: Optional[Exception] = None
    for locator in locators:
        try:
            locator.first.wait_for(state="visible", timeout=timeout_ms)
            locator.first.fill(value, timeout=timeout_ms)
            return
        except PlaywrightTimeoutError as error:
            last_error = error
            continue
    raise RuntimeError(f"Could not find {description}.") from last_error


def _select_option_label_case_insensitive(
    select_locator: Locator,
    desired_label: str,
) -> None:
    desired = re.sub(r"\s+", " ", desired_label).strip().lower()
    options = select_locator.locator("option")
    option_count = options.count()
    for index in range(option_count):
        option = options.nth(index)
        label = option.text_content() or ""
        normalized_label = re.sub(r"\s+", " ", label).strip().lower()
        if normalized_label == desired:
            value = option.get_attribute("value")
            if value is not None:
                select_locator.select_option(value=value)
                return
            select_locator.select_option(label=label)
            return

    select_locator.select_option(label=desired_label)


@dataclass(frozen=True)
class Config:
    helm_url: str
    email: str
    password: str
    debug: bool

    @staticmethod
    def load(dotenv_path: Path = DOTENV_PATH) -> "Config":
        load_dotenv(dotenv_path=dotenv_path)

        return Config(
            helm_url=(
                os.getenv("HELM_URL") or "https://mybeautyandcareltd.myhelm.app/"
            ).strip(),
            email=_require_env("HELM_EMAIL").strip(),
            password=_require_env("HELM_PASSWORD"),
            debug=_env_flag("DEBUG", default=False),
        )


class LoginFlow:
    def __init__(self, page: Page, config: Config):
        self.page = page
        self.config = config

    def open(self) -> None:
        self.page.goto(self.config.helm_url, wait_until="domcontentloaded")

    def fill_credentials(self) -> None:
        _fill_first_visible(
            [
                self.page.get_by_label("Email", exact=False),
                self.page.get_by_placeholder(re.compile("email", re.I)),
                self.page.locator("input[type='email']"),
                self.page.locator("input[name*='email' i]"),
            ],
            self.config.email,
            "email input",
        )

        _fill_first_visible(
            [
                self.page.get_by_label("Password", exact=False),
                self.page.get_by_placeholder(re.compile("password", re.I)),
                self.page.locator("input[type='password']"),
                self.page.locator("input[name*='password' i]"),
            ],
            self.config.password,
            "password input",
        )

    def submit(self) -> None:
        _click_first_visible(
            [
                self.page.get_by_role("button", name=re.compile("log in|login", re.I)),
                self.page.get_by_role("button", name=re.compile("sign in", re.I)),
            ],
            "login button",
        )

    def _login_error_message(self) -> Optional[str]:
        candidates = [
            self.page.get_by_text(
                re.compile(
                    r"Login failed!\s*Unable to verify your login credentials\.?",
                    re.I,
                )
            ),
            self.page.get_by_text(re.compile(r"\bLogin failed\b", re.I)),
            self.page.get_by_text(
                re.compile(r"Unable to verify your login credentials", re.I)
            ),
            self.page.locator(".alert.alert-danger"),
            self.page.locator(".alert-danger"),
        ]
        for locator in candidates:
            try:
                if locator.count() > 0 and locator.first.is_visible():
                    text = locator.first.text_content() or ""
                    text = re.sub(r"\s+", " ", text).strip()
                    return text or "Login failed"
            except PlaywrightTimeoutError:
                continue
        return None

    def verify(self, timeout_ms: int = 15000) -> None:
        self.page.wait_for_timeout(500)
        start_time = self.page.evaluate("Date.now()")

        while self.page.evaluate("Date.now()") - start_time < timeout_ms:
            error_text = self._login_error_message()
            if error_text:
                try:
                    self.page.screenshot(path="login_failed.png", full_page=True)
                except Exception:
                    pass
                raise SystemExit(
                    f"Login failed: {error_text}. Check HELM_EMAIL/HELM_PASSWORD in your .env file."
                )

            app_chrome = self.page.locator(
                "div.sidebar, ul.acc-menu, nav[role='navigation']"
            )
            login_form = self.page.locator(
                "input[type='password'], input[name*='password' i]"
            )
            try:
                if app_chrome.count() > 0 and app_chrome.first.is_visible():
                    return
                if login_form.count() == 0:
                    return
            except PlaywrightTimeoutError:
                pass

            self.page.wait_for_timeout(250)

        error_text = self._login_error_message()
        if error_text:
            try:
                self.page.screenshot(path="login_failed.png", full_page=True)
            except Exception:
                pass
            raise SystemExit(
                f"Login failed: {error_text}. Check HELM_EMAIL/HELM_PASSWORD in your .env file."
            )

        raise SystemExit(
            "Login did not complete within the expected time. If credentials are correct, the site may require extra steps (e.g., CAPTCHA/2FA) or the page UI changed."
        )


class SettingsFlow:
    def __init__(self, page: Page):
        self.page = page

    def open_settings_menu(self) -> None:
        _click_first_visible(
            [
                self.page.locator("div.sidebar a[href='/settings/menu']"),
                self.page.locator("a[href='/settings/menu']"),
                self.page.locator("a[href*='/settings/menu' i]"),
                self.page.get_by_role("link", name=re.compile("settings", re.I)),
                self.page.get_by_role("button", name=re.compile("settings", re.I)),
                self.page.get_by_text(re.compile(r"^Settings$", re.I)),
                self.page.locator("a[href*='setting' i]"),
                self.page.locator("button[aria-label*='setting' i]"),
            ],
            "Settings navigation item",
            timeout_ms=10000,
        )
        _wait_for_network_idle(self.page)

    def open_general_settings(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    'div.settings-page div.setting-option[onclick*="/settings/index"]'
                ),
                self.page.locator('div.setting-option[onclick*="/settings/index"]'),
                self.page.locator(
                    "div.setting-option:has(span:text-is('General Settings'))"
                ),
                self.page.get_by_role(
                    "button", name=re.compile("general settings", re.I)
                ),
                self.page.get_by_role(
                    "link", name=re.compile("general settings", re.I)
                ),
                self.page.get_by_text(re.compile(r"^General Settings$", re.I)),
                self.page.locator("text=/General Settings/i"),
            ],
            "General Settings card",
            timeout_ms=10000,
        )
        _wait_for_network_idle(self.page)

    def open_picking_section(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "button.accordion-header[aria-controls='collapse-picking']"
                ),
                self.page.locator("button[aria-controls='collapse-picking']"),
                self.page.locator(
                    "button.accordion-header:has(h2.header-title:text-is('Picking'))"
                ),
                self.page.get_by_role("button", name=re.compile(r"^Picking$", re.I)),
                self.page.get_by_text(re.compile(r"^Picking$", re.I)),
                self.page.locator("text=/^Picking$/i"),
            ],
            "Picking section",
            timeout_ms=10000,
        )
        _wait_for_network_idle(self.page)

    def set_single_item_multi_action_to_single_picks(self) -> None:
        select = self.page.locator("select#single_item_multi_action").first
        try:
            select.wait_for(state="visible", timeout=10000)
            _select_option_label_case_insensitive(select, "Included In Single Picks")
            return
        except PlaywrightTimeoutError:
            pass

        label = self.page.locator(
            "label[for='single_item_multi_action']",
            has_text=re.compile(r"^Single Item Multi Action:?\s*$", re.I),
        ).first
        label.wait_for(state="visible", timeout=10000)
        linked_select = self.page.locator("#single_item_multi_action").first
        _select_option_label_case_insensitive(
            linked_select,
            "Included In Single Picks",
        )

    def save(self) -> None:
        _click_first_visible(
            [
                self.page.locator("button#save-settings-button"),
                self.page.locator("#save-settings-button"),
                self.page.get_by_role("button", name=re.compile("save settings", re.I)),
                self.page.get_by_role("button", name=re.compile("save setting", re.I)),
                self.page.get_by_text(re.compile(r"^Save Settings$", re.I)),
                self.page.get_by_text(re.compile(r"^Save Setting$", re.I)),
            ],
            "Save Settings button",
            timeout_ms=10000,
        )
        _wait_for_network_idle(self.page)


class OrdersFlow:
    def __init__(self, page: Page):
        self.page = page

    def open_orders(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "ul.acc-menu a[href='/orders/index']:has(span:text-is('Orders'))"
                ),
                self.page.locator("a[href='/orders/index']"),
                self.page.locator("a[href*='/orders/index' i]"),
                self.page.get_by_role("link", name=re.compile(r"^Orders$", re.I)),
                self.page.get_by_text(re.compile(r"^Orders$", re.I)),
                self.page.locator("a[href*='orders' i]"),
            ],
            "Orders navigation item",
            timeout_ms=10000,
        )
        _wait_for_network_idle(self.page)

    def open_filters_dropdown(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "div[data-dropdown='filter-actions'] button#clear-button"
                ),
                self.page.locator(
                    "button#clear-button[data-dropdown='filter-actions']"
                ),
                self.page.locator(
                    "button.custom-dropdown__trigger[data-dropdown='filter-actions']"
                ),
                self.page.locator(
                    "div.custom-dropdown[data-dropdown='filter-actions'] button"
                ),
            ],
            "Apply Filters dropdown",
            timeout_ms=10000,
        )

    def clear_filters(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "div[data-dropdown='filter-actions'] "
                    "button.dropdown-action__item",
                    has_text=re.compile(r"Clear Filters", re.I),
                ),
                self.page.get_by_role(
                    "button", name=re.compile(r"Clear Filters", re.I)
                ),
                self.page.get_by_text(re.compile(r"^Clear Filters$", re.I)),
            ],
            "Clear Filters button",
            timeout_ms=10000,
        )
        _wait_for_network_idle(self.page)

    def open_saved_filters(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "div[data-dropdown='saved-filters'] button#saved-filters"
                ),
                self.page.locator(
                    "button#saved-filters[data-dropdown='saved-filters']"
                ),
                self.page.locator(
                    "button.custom-dropdown__trigger[data-dropdown='saved-filters']"
                ),
                self.page.get_by_role(
                    "button", name=re.compile(r"Saved Filters", re.I)
                ),
                self.page.get_by_text(re.compile(r"^Saved Filters$", re.I)),
            ],
            "Saved Filters button",
            timeout_ms=10000,
        )

    def open_saved_filter_input(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "div[data-dropdown='saved-filters'] "
                    "input.select-element__input[data-select='filter_id']"
                ),
                self.page.locator(
                    "div.select-element[data-select='filter_id'] "
                    "input[data-type='label']"
                ),
                self.page.get_by_placeholder(
                    re.compile(r"Choose a saved filter", re.I)
                ),
                self.page.locator("input[name='filter_id']"),
            ],
            "Choose a saved filter input",
            timeout_ms=10000,
        )

    def choose_despatch_ready_saved_filter(self) -> None:
        filter_name = "Despatch Ready - Pregen Success - To Allocate"
        _click_first_visible(
            [
                self.page.locator(
                    "div.select-element__option[data-select='filter_id']"
                    "[data-value='9'][data-label='Despatch Ready - Pregen Success - To Allocate']"
                ),
                self.page.locator(
                    "div.select-element__option[data-select='filter_id']",
                    has_text=re.compile(rf"^{re.escape(filter_name)}$", re.I),
                ),
                self.page.get_by_text(re.compile(rf"^{re.escape(filter_name)}$", re.I)),
            ],
            f"saved filter '{filter_name}'",
            timeout_ms=10000,
        )

    def apply_saved_filter(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "div[data-dropdown='saved-filters'] "
                    "button[name='load_filter'][value='Apply']"
                ),
                self.page.locator("button[name='load_filter']"),
                self.page.get_by_role("button", name=re.compile(r"^Apply$", re.I)),
                self.page.get_by_text(re.compile(r"^Apply$", re.I)),
            ],
            "saved filter Apply button",
            timeout_ms=10000,
        )
        _wait_for_network_idle(self.page)

    def set_records_per_page_to_total(self) -> None:
        per_page_input = self.page.locator("input#per-page").first
        per_page_input.wait_for(state="visible", timeout=10000)

        record_text = self.page.locator("span.check-filtered.table-select-all").first
        record_text.wait_for(state="visible", timeout=10000)
        text = record_text.text_content() or ""
        match = re.search(r"/\s*([\d,]+)\s+records", text, re.I)
        if not match:
            raise RuntimeError(f"Could not find total records count in: {text!r}")

        total_records = match.group(1).replace(",", "")
        per_page_input.fill(total_records, timeout=10000)
        per_page_input.press("Enter", timeout=10000)
        _wait_for_network_idle(self.page)

    def select_all_on_page(self) -> None:
        checkbox = self.page.locator("input.check-all-on-page.processible").first
        checkbox.wait_for(state="visible", timeout=10000)
        if not checkbox.is_checked():
            checkbox.click(timeout=10000)

    def open_bulk_action(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "div[data-dropdown='bulk-action'] "
                    "button.custom-dropdown__trigger[data-dropdown='bulk-action']"
                ),
                self.page.locator("button[data-dropdown='bulk-action']"),
                self.page.get_by_role(
                    "button", name=re.compile(r"Select Bulk Action", re.I)
                ),
                self.page.get_by_text(re.compile(r"^Select Bulk Action$", re.I)),
            ],
            "Select Bulk Action button",
            timeout_ms=10000,
        )

    def select_allocate_stock(self) -> None:
        bulk_action = self.page.locator("select[name='bulk_action']").first
        bulk_action.wait_for(state="visible", timeout=10000)
        bulk_action.select_option(value="try_allocation")

    def submit_bulk_action(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "div[data-dropdown='bulk-action'] "
                    "button[onclick='startBulkAction()']"
                ),
                self.page.locator("button[onclick='startBulkAction()']"),
                self.page.get_by_role(
                    "button", name=re.compile(r"^Submit Action$", re.I)
                ),
                self.page.get_by_text(re.compile(r"^Submit Action$", re.I)),
            ],
            "Submit Action button",
            timeout_ms=10000,
        )
        _wait_for_network_idle(self.page)

    def open_filters_panel(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "button.dc-main-filters-trigger[onclick='toggleMainFilters(this)']"
                ),
                self.page.locator("button.dc-main-filters-trigger"),
                self.page.get_by_role("button", name=re.compile(r"Filters", re.I)),
                self.page.get_by_text(re.compile(r"^Filters$", re.I)),
            ],
            "Filters button",
            timeout_ms=10000,
        )
        self.page.locator("#mainFiltersContent").first.wait_for(
            state="visible",
            timeout=10000,
        )

    def open_allocation_status_filter(self) -> None:
        _click_first_visible(
            [
                self.page.locator(
                    "#mainFiltersContent "
                    "div.custom-dropdown[data-filter='allocation_status'] "
                    "div.custom-dropdown__trigger.filter-trigger"
                ),
                self.page.locator(
                    "div[data-dropdown='allocation_status'] "
                    "div[data-key='allocation_status']"
                ),
                self.page.locator(
                    "div.custom-dropdown[data-filter='allocation_status'] "
                    "div.filter-trigger"
                ),
                self.page.get_by_text(re.compile(r"^Allocation Status$", re.I)),
            ],
            "Allocation Status filter",
            timeout_ms=10000,
        )
        self.page.locator(
            "div.custom-dropdown[data-filter='allocation_status'] "
            "div.custom-dropdown__content"
        ).first.wait_for(state="visible", timeout=10000)

    def select_fully_allocated(self) -> None:
        checkbox = self.page.locator(
            "div.custom-select__items[data-filter='allocation_status'] "
            "input[name='filters[allocation_status][]'][value='2']"
        ).first
        checkbox.wait_for(state="visible", timeout=10000)
        if not checkbox.is_checked():
            checkbox.click(timeout=10000)


def run(config: Config) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            _log_info(config.debug, f"Loaded .env from: {DOTENV_PATH}")
            _log_info(config.debug, f"HELM_URL: {config.helm_url}")
            _log_info(config.debug, f"HELM_EMAIL: {config.email}")

            login = LoginFlow(page, config)
            login.open()
            login.fill_credentials()

            if config.debug:
                try:
                    email_value = page.locator(
                        "input[type='email']"
                    ).first.input_value()
                except Exception:
                    email_value = ""
                try:
                    password_value = page.locator(
                        "input[type='password']"
                    ).first.input_value()
                except Exception:
                    password_value = ""
                _log_info(config.debug, f"Email field filled: {bool(email_value)}")
                _log_info(config.debug, f"Password field length: {len(password_value)}")

            login.submit()
            page.wait_for_load_state("domcontentloaded")
            login.verify()
            _log_step("Step 1: Login")

            settings = SettingsFlow(page)
            settings.open_settings_menu()
            _log_step("Step 2: Click Settings")

            settings.open_general_settings()
            _log_step("Step 3: Click General Settings")

            settings.open_picking_section()
            _log_step("Step 4: Click Picking")

            settings.set_single_item_multi_action_to_single_picks()
            _log_step(
                'Step 5: Set Single Item Multi Action to "Included In Single Picks"'
            )

            settings.save()
            _log_step("Step 6: Click Save Settings")

            orders = OrdersFlow(page)
            orders.open_orders()
            _log_step("Step 7: Click Orders")

            orders.open_filters_dropdown()
            _log_step("Step 8: Click filter actions dropdown")

            orders.clear_filters()
            _log_step("Step 9: Click Clear Filters")

            orders.open_saved_filters()
            _log_step("Step 10: Click Saved Filters")

            orders.open_saved_filter_input()
            _log_step("Step 11: Click Choose a saved filter input")

            orders.choose_despatch_ready_saved_filter()
            _log_step(
                "Step 12: Click saved filter "
                "'Despatch Ready - Pregen Success - To Allocate'"
            )

            orders.apply_saved_filter()
            _log_step("Step 13: Click Apply")

            orders.set_records_per_page_to_total()
            _log_step("Step 14: Set records per page to full record count")

            orders.select_all_on_page()
            _log_step("Step 15: Click select-all checkbox")

            orders.open_bulk_action()
            _log_step("Step 16: Click Select Bulk Action")

            orders.select_allocate_stock()
            _log_step("Step 17: Select Allocate Stock")

            orders.submit_bulk_action()
            _log_step("Step 18: Click Submit Action")

            orders.open_filters_panel()
            _log_step("Step 19: Click Filters")

            orders.open_allocation_status_filter()
            _log_step("Step 20: Click Allocation Status")

            orders.select_fully_allocated()
            _log_step("Step 21: Click Fully Allocated")
        finally:
            try:
                context.close()
            finally:
                browser.close()


if __name__ == "__main__":
    run(Config.load())
