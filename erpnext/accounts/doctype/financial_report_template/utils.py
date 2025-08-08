# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import ast
from functools import reduce
from typing import Any

import frappe
from frappe import _
from frappe.query_builder import Case
from frappe.query_builder.functions import Sum
from frappe.utils import cstr, date_diff, getdate

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
	get_dimension_with_children,
)
from erpnext.accounts.report.financial_statements import (
	get_cost_centers_with_children,
)


class PeriodAccountDataCollector:
	"""Collects account data across multiple periods efficiently."""

	def __init__(self, filters: dict[str, Any], periods: list[dict]):
		self.filters = filters
		self.periods = periods
		self.company = filters.get("company")
		self.data_requests = []

	def add_data_request(self, row, accounts: list[str] | None = None):
		if not accounts and row.calculation_formula:
			accounts = self.find_matching_accounts(row.calculation_formula)
		elif not accounts:
			accounts = []

		request = {
			"row": row,
			"accounts": accounts,
			"data_source": row.data_source,
			"reference_code": row.reference_code,
		}
		self.data_requests.append(request)

	def process_all_requests(self) -> dict[str, list[float]]:
		"""
		Process all data requests in a single optimized query.
		Steps: collect accounts → fetch balances → distribute results
		"""
		if not self.data_requests:
			return {}

		all_accounts = set()
		for request in self.data_requests:
			all_accounts.update(request["accounts"])

		all_accounts = list(all_accounts)
		if not all_accounts:
			return {
				req["reference_code"]: [0.0] * len(self.periods)
				for req in self.data_requests
				if req["reference_code"]
			}

		balance_processor = BalanceProcessor(self.filters, self.periods)
		account_balances = balance_processor.fetch_all_balances(all_accounts)

		results = {}
		for request in self.data_requests:
			if request["reference_code"]:
				period_values = balance_processor.calculate_totals(request, account_balances)
				results[request["reference_code"]] = period_values

		return results

	def find_matching_accounts(self, filter_formula: str) -> list[str]:
		"""Find accounts matching filter criteria."""
		filter_parser = FilterExpressionParser()
		criteria = filter_parser.parse(filter_formula)

		account = frappe.qb.DocType("Account")
		query = frappe.qb.from_(account).select(account.name).where(account.disabled == 0)

		if self.company:
			query = query.where(account.company == self.company)

		where_condition = filter_parser.build_condition(criteria, account)
		if where_condition is not None:
			query = query.where(where_condition)

		query = query.orderby(account.name)
		result = query.run(as_dict=True)
		return [row.name for row in result]


class BalanceProcessor:
	def __init__(self, filters: dict, periods: list[dict]):
		self.filters = filters
		self.periods = periods
		self.company = filters.get("company")

	def fetch_all_balances(self, accounts: list[str]) -> dict:
		"""
		Fetch account balances for all periods with optimization.
		Steps: get opening balances → fetch GL entries → calculate running totals

		Returns dict: {account: {period_key: {opening, closing, movement}}}
		"""
		ignore_closing_balances = frappe.get_single_value(
			"Accounts Settings", "ignore_account_closing_balance"
		)
		first_period_start = getdate(self.periods[0]["from_date"])
		balances_data = {}

		# Step 1: Get opening balances from Account Closing Balance if available
		if not ignore_closing_balances:
			last_closing_voucher = frappe.db.get_all(
				"Period Closing Voucher",
				filters={
					"docstatus": 1,
					"company": self.company,
					"period_end_date": ("<", first_period_start),
				},
				fields=["period_end_date", "name"],
				order_by="period_end_date desc",
				limit=1,
			)

			if last_closing_voucher:
				closing_balances = self._get_closing_balances(accounts, last_closing_voucher[0].name)

				if closing_balances:
					balances_data = self._rebase_closing_balances(
						balances_data, closing_balances, last_closing_voucher[0].period_end_date
					)

		else:
			# TODO: Implement opening balance retrieval using rebase closing balances
			pass

		# Step 2: Get GL Entry data (from adjusted date or original period start)
		gl_data = self._get_gl_movements(accounts)

		# Step 3: Calculate running balances
		balances_data = self._calculate_running_balances(balances_data, gl_data)

		return balances_data

	def _get_closing_balances(self, account_names: list[str], closing_voucher: str) -> dict:
		acb_table = frappe.qb.DocType("Account Closing Balance")

		query = (
			frappe.qb.from_(acb_table)
			.select(
				acb_table.account,
				(acb_table.debit - acb_table.credit).as_("balance"),
			)
			.where(acb_table.company == self.company)
			.where(acb_table.account.isin(account_names))
			.where(acb_table.period_closing_voucher == closing_voucher)
		)

		query = self._apply_filters(query, acb_table)
		results = query.run(as_dict=True)

		return {row["account"]: row["balance"] for row in results}

	def _rebase_closing_balances(self, balances_data: dict, closing_data: dict, closing_date: str) -> dict:
		"""Rebase closing balances to align with the report start date."""
		if not closing_data:
			return balances_data

		first_period_key = self.periods[0]["key"]
		report_start = getdate(self.periods[0]["from_date"])
		closing_end = getdate(closing_date)

		has_gap = date_diff(report_start, closing_end) > 1

		gap_movements = {}
		if has_gap:
			gap_movements = self._get_gap_movements(list(closing_data.keys()), closing_date, report_start)

		for account, closing_balance in closing_data.items():
			if account not in balances_data:
				balances_data[account] = {}
			if first_period_key not in balances_data[account]:
				balances_data[account][first_period_key] = {}

			gap_adjustment = gap_movements.get(account, 0.0) if has_gap else 0.0
			opening_balance = closing_balance + gap_adjustment

			balances_data[account][first_period_key]["opening"] = opening_balance

		return balances_data

	def _get_gap_movements(self, account_names: list[str], from_date: str, to_date: str) -> dict:
		query, gl_table = self._build_gl_base_query(account_names)

		query = (
			query.select(Sum(gl_table.debit - gl_table.credit).as_("movement"))
			.where(gl_table.posting_date > from_date)
			.where(gl_table.posting_date < to_date)
		)

		results = query.run(as_dict=True)
		return {row["account"]: row["movement"] or 0.0 for row in results}

	def _get_gl_movements(self, account_names: list[str]) -> list:
		query, gl_table = self._build_gl_base_query(account_names)

		start_date = self.periods[0]["from_date"]
		query = query.where(gl_table.posting_date >= start_date)

		for period in self.periods:
			period_key = period["key"]
			period_start = period["from_date"]
			period_end = period["to_date"]

			movement_column = Sum(
				Case()
				.when(
					(gl_table.posting_date >= period_start) & (gl_table.posting_date <= period_end),
					gl_table.debit - gl_table.credit,
				)
				.else_(0)
			).as_(f"{period_key}_movement")
			query = query.select(movement_column)

		return self._execute_with_permissions(query)

	def _calculate_running_balances(self, balances_data: dict, gl_data: list) -> dict:
		for row in gl_data:
			account = row["account"]

			if account not in balances_data:
				balances_data[account] = {}

			running_total = 0.0

			first_period_key = self.periods[0]["key"]
			if (
				first_period_key in balances_data.get(account, {})
				and "opening" in balances_data[account][first_period_key]
			):
				running_total = balances_data[account][first_period_key]["opening"]

			for period in self.periods:
				period_key = period["key"]
				movement = row.get(f"{period_key}_movement", 0.0) or 0.0

				if period_key not in balances_data[account]:
					balances_data[account][period_key] = {}

				balances_data[account][period_key]["opening"] = running_total
				balances_data[account][period_key]["movement"] = movement
				balances_data[account][period_key]["closing"] = running_total + movement

				running_total += movement

		return balances_data

	def _build_gl_base_query(self, account_names: list[str]) -> tuple:
		gl_table = frappe.qb.DocType("GL Entry")

		query = (
			frappe.qb.from_(gl_table)
			.select(gl_table.account)
			.where(gl_table.company == self.company)
			.where(gl_table.is_cancelled == 0)
			.where(gl_table.account.isin(account_names))
			.groupby(gl_table.account)
		)

		if not frappe.get_single_value("Accounts Settings", "ignore_is_opening_check_for_reporting"):
			query = query.where(gl_table.is_opening == "No")

		query = self._apply_filters(query, gl_table)
		return query, gl_table

	def _apply_filters(self, query, table):
		"""Apply standard financial filters to query."""
		if self.filters.get("ignore_closing_entries"):
			if hasattr(table, "is_period_closing_voucher_entry"):
				query = query.where(table.is_period_closing_voucher_entry == 0)
			else:
				query = query.where(table.voucher_type != "Period Closing Voucher")

		if self.filters.get("project"):
			if not isinstance(self.filters.get("project"), list):
				self.filters.project = frappe.parse_json(self.filters.get("project"))
			query = query.where(table.project.isin(self.filters.project))

		if self.filters.get("cost_center"):
			self.filters.cost_center = get_cost_centers_with_children(self.filters.cost_center)
			query = query.where(table.cost_center.isin(self.filters.cost_center))

		if self.filters.get("include_default_book_entries"):
			default_book = frappe.get_cached_value("Company", self.filters.company, "default_finance_book")

			if (
				self.filters.finance_book
				and default_book
				and cstr(self.filters.finance_book) != cstr(default_book)
			):
				frappe.throw(
					_("To use a different finance book, please uncheck 'Include Default FB Entries'")
				)

			query = query.where(
				(table.finance_book.isin([cstr(self.filters.finance_book), cstr(default_book), ""]))
				| (table.finance_book.isnull())
			)
		else:
			query = query.where(
				(table.finance_book.isin([cstr(self.filters.finance_book), ""]))
				| (table.finance_book.isnull())
			)

		dimensions = get_accounting_dimensions(as_list=False)
		for dimension in dimensions:
			if self.filters.get(dimension.fieldname):
				if frappe.get_cached_value("DocType", dimension.document_type, "is_tree"):
					self.filters[dimension.fieldname] = get_dimension_with_children(
						dimension.document_type, self.filters.get(dimension.fieldname)
					)

				query = query.where(table[dimension.fieldname].isin(self.filters.get(dimension.fieldname)))

		return query

	def _execute_with_permissions(self, query):
		query_sql = query.walk()

		from frappe.desk.reportview import build_match_conditions

		user_conditions = build_match_conditions("GL Entry")

		if user_conditions:
			final_query = f"({query_sql}) AND ({user_conditions})"
			return frappe.db.sql(final_query, as_dict=True)
		else:
			return query.run(as_dict=True)

	def calculate_totals(self, request: dict, account_data: dict) -> list[float]:
		accounts = request["accounts"]
		data_source = request["data_source"]
		totals = []

		for period in self.periods:
			period_key = period["key"]
			period_sum = 0.0

			for account in accounts:
				if account in account_data and period_key in account_data[account]:
					balance_info = account_data[account][period_key]

					if data_source == "Opening Balance":
						period_sum += balance_info["opening"]
					elif data_source == "Closing Balance":
						period_sum += balance_info["closing"]
					elif data_source == "Period Movement":
						period_sum += balance_info["movement"]

			totals.append(period_sum)

		return totals


class FilterExpressionParser:
	"""Converts filter formulas into database query conditions."""

	def parse(self, formula: str) -> dict:
		"""
		Parse filter formula into structured criteria.
		Supports: ["field", "op", "value"] and {"and/or": [conditions]}
		"""
		parsed_formula = ast.literal_eval(formula)

		if isinstance(parsed_formula, dict):
			return self._parse_logical_condition(parsed_formula)

		elif self._is_simple_condition(parsed_formula):
			return {
				"type": "simple",
				"field": parsed_formula[0],
				"operator": parsed_formula[1],
				"value": parsed_formula[2],
			}

		return {}

	def _parse_logical_condition(self, condition_dict: dict) -> dict:
		if not isinstance(condition_dict, dict) or len(condition_dict) != 1:
			return {"type": "invalid"}

		logical_op = next(iter(condition_dict.keys())).lower()
		sub_conditions = condition_dict[logical_op]

		if logical_op not in ["and", "or"] or not isinstance(sub_conditions, list) or len(sub_conditions) < 2:
			return {"type": "invalid"}

		parsed_sub_conditions = []
		for condition in sub_conditions:
			if isinstance(condition, dict):
				parsed_condition = self._parse_logical_condition(condition)
			elif self._is_simple_condition(condition):
				parsed_condition = {
					"type": "simple",
					"field": condition[0],
					"operator": condition[1],
					"value": condition[2],
				}
			else:
				parsed_condition = {"type": "invalid"}

			parsed_sub_conditions.append(parsed_condition)

		return {"type": "logical", "operator": logical_op, "conditions": parsed_sub_conditions}

	def _is_simple_condition(self, parsed) -> bool:
		return (
			isinstance(parsed, list)
			and len(parsed) == 3
			and isinstance(parsed[0], str)
			and isinstance(parsed[1], str)
		)

	def build_condition(self, criteria: dict, table):
		"""Convert criteria into database query conditions."""
		if not criteria or criteria.get("type") == "invalid":
			return None

		if criteria["type"] == "simple":
			return self._create_field_condition(criteria, table)

		elif criteria["type"] == "logical":
			conditions = []
			for sub_criteria in criteria["conditions"]:
				condition = self.build_condition(sub_criteria, table)
				if condition is not None:
					conditions.append(condition)

			if not conditions:
				return None

			if criteria["operator"] == "and":
				return reduce(lambda a, b: a & b, conditions)
			elif criteria["operator"] == "or":
				return reduce(lambda a, b: a | b, conditions)

		return None

	def _create_field_condition(self, criteria: dict, table):
		field_name = criteria["field"]
		operator = criteria["operator"]
		value = criteria["value"]

		if not hasattr(table, field_name):
			return None

		field = getattr(table, field_name)

		if operator in ["=", "=="]:
			return field == value
		elif operator in ["!=", "<>"]:
			return field != value
		elif operator == "in" and isinstance(value, list):
			return field.isin(value)
		elif operator == "not in" and isinstance(value, list):
			return field.notin(value)
		elif operator == "like":
			return field.like(f"%{value}%")
		elif operator == "not like":
			return field.not_like(f"%{value}%")
		elif operator == "is":
			if value is None or (isinstance(value, str) and value.lower() == "set"):
				return field.isnull()
			elif value is None or (isinstance(value, str) and value.lower() == "not set"):
				return field.isnotnull()
			else:
				return field == value

		return None
