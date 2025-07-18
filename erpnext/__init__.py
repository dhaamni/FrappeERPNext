import functools
import inspect
from typing import TypeVar, Callable, Optional, Any

import frappe
from frappe.model.document import Document
from frappe.utils.user import is_website_user

__version__ = "16.0.0-dev"


def get_default_company(user: Optional[str] = None) -> Optional[str]:
	"""Get default company for the user."""
	from frappe.defaults import get_user_default_as_list

	user = user or frappe.session.user
	companies = get_user_default_as_list("company", user)
	if companies:
		return companies[0]

	return frappe.db.get_single_value("Global Defaults", "default_company")


def get_default_currency() -> Optional[str]:
	"""Returns the currency of the default company."""
	company = get_default_company()
	if company:
		return frappe.get_cached_value("Company", company, "default_currency")
	return None


def get_default_cost_center(company: Optional[str]) -> Optional[str]:
	"""Returns the default cost center of the company."""
	if not company:
		return None

	frappe.flags.company_cost_center = getattr(frappe.flags, "company_cost_center", {})
	if company not in frappe.flags.company_cost_center:
		frappe.flags.company_cost_center[company] = frappe.get_cached_value("Company", company, "cost_center")

	return frappe.flags.company_cost_center[company]


def get_company_currency(company: str) -> Optional[str]:
	"""Returns the default company currency."""
	frappe.flags.company_currency = getattr(frappe.flags, "company_currency", {})
	if company not in frappe.flags.company_currency:
		frappe.flags.company_currency[company] = frappe.db.get_value("Company", company, "default_currency", cache=True)

	return frappe.flags.company_currency[company]


def set_perpetual_inventory(enable: int = 1, company: Optional[str] = None) -> None:
	"""Enable or disable perpetual inventory for the given company."""
	company = company or ("_Test Company" if frappe.in_test else get_default_company())
	doc = frappe.get_cached_doc("Company", company)
	doc.enable_perpetual_inventory = enable
	doc.save()


def encode_company_abbr(name: str, company: Optional[str] = None, abbr: Optional[str] = None) -> str:
	"""Returns name encoded with company abbreviation."""
	company_abbr = abbr or frappe.get_cached_value("Company", company, "abbr")
	parts = name.rsplit(" - ", 1)
	if parts[-1].lower() != company_abbr.lower():
		parts.append(company_abbr)
	return " - ".join(parts)


def is_perpetual_inventory_enabled(company: Optional[str]) -> bool:
	"""Checks if perpetual inventory is enabled for the company."""
	company = company or ("_Test Company" if frappe.in_test else get_default_company())

	frappe.local.enable_perpetual_inventory = getattr(frappe.local, "enable_perpetual_inventory", {})
	if company not in frappe.local.enable_perpetual_inventory:
		frappe.local.enable_perpetual_inventory[company] = (
			frappe.get_cached_value("Company", company, "enable_perpetual_inventory") or 0
		)
	return bool(frappe.local.enable_perpetual_inventory[company])


def get_default_finance_book(company: Optional[str] = None) -> Optional[str]:
	"""Returns the default finance book for the company."""
	company = company or get_default_company()
	frappe.local.default_finance_book = getattr(frappe.local, "default_finance_book", {})

	if company not in frappe.local.default_finance_book:
		frappe.local.default_finance_book[company] = frappe.get_cached_value("Company", company, "default_finance_book")

	return frappe.local.default_finance_book[company]


def get_party_account_type(party_type: str) -> str:
	"""Returns the account type linked with the given party type."""
	frappe.local.party_account_types = getattr(frappe.local, "party_account_types", {})

	if party_type not in frappe.local.party_account_types:
		frappe.local.party_account_types[party_type] = (
			frappe.db.get_value("Party Type", party_type, "account_type") or ""
		)
	return frappe.local.party_account_types[party_type]


def get_region(company: Optional[str] = None) -> Optional[str]:
	"""Return the default country based on flag, company or global settings."""
	company = company or frappe.flags.get("company")
	if company:
		return frappe.get_cached_value("Company", company, "country")
	return frappe.flags.get("country") or frappe.get_system_settings("country")


def allow_regional(fn: Callable) -> Callable:
	"""Decorator to make a function regionally overridable based on region hooks."""

	@functools.wraps(fn)
	def caller(*args: Any, **kwargs: Any) -> Any:
		overrides = frappe.get_hooks("regional_overrides", {}).get(get_region())
		function_path = f"{inspect.getmodule(fn).__name__}.{fn.__name__}"

		if not overrides or function_path not in overrides:
			return fn(*args, **kwargs)

		# Use the last installed app's override
		return frappe.get_attr(overrides[function_path][-1])(*args, **kwargs)

	return caller


def check_app_permission() -> bool:
	"""Check if current user has app-level permissions."""
	if frappe.session.user == "Administrator":
		return True
	return not is_website_user()


T = TypeVar("T")


def normalize_ctx_input(T: type) -> Callable:
	"""
	Normalizes the first argument (ctx) of the decorated function by:
	- Converting Document objects to dictionaries
	- Parsing JSON strings
	- Casting the result to the specified type T
	"""

	def decorator(func: Callable) -> Callable:
		@functools.wraps(func, assigned=(a for a in functools.WRAPPER_ASSIGNMENTS if a != "__annotations__"))
		def wrapper(ctx: T | Document | dict | str, *args: Any, **kwargs: Any) -> Any:
			if isinstance(ctx, Document):
				ctx = T(**ctx.as_dict())
			elif isinstance(ctx, dict):
				ctx = T(**ctx)
			else:
				ctx = T(**frappe.parse_json(ctx))

			return func(ctx, *args, **kwargs)

		wrapper.__annotations__.update({k: v for k, v in func.__annotations__.items() if k != "ctx"})
		return wrapper

	return decorator
