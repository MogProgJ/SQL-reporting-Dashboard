"""Northwind-style order workbook adapter.

Transforms workbooks like ``orders_frostonline.xlsx`` — which contain sheets
such as *categories*, *customers*, *employees*, *orders*, *ordersdetails*,
*products*, *shippers*, *suppliers* — into the canonical Order Reporting model.

Key mapping decisions (documented and surfaced to the user):
- ``ordersdetails`` / ``orderdetails`` / ``order_details`` → ``order_items``
- ``CustomerName`` / ``CompanyName`` / ``ContactName`` → ``customers.name``
- ``CategoryName`` → ``categories.name``
- ``ProductName`` → ``products.name``
- ``OrderDate`` → ``orders.created_at``
- ``UnitPrice`` / ``Price`` → ``unit_price_cents`` (dollars × 100)
- If no ``status`` column exists → default to ``"completed"``
- ``employees``, ``shippers``, ``suppliers`` sheets are ignored
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd

from adapters import (
    AdapterPlan,
    AdapterResult,
    BaseAdapter,
    FieldMapping,
    register_adapter,
)
from file_profiler import FileProfile, ProfileFamily


class NorthwindOrderAdapter(BaseAdapter):
    name = "northwind_order_excel"
    description = "Northwind-style order workbook (close to canonical but needs column mapping)."
    profile_family = ProfileFamily.ORDER_REPORTING

    # Sheet aliases: Northwind name → canonical entity
    _SHEET_ALIASES: dict[str, str] = {
        "orderdetails": "order_items",
        "ordersdetails": "order_items",
        "order_details": "order_items",
        "order details": "order_items",
        "categories": "categories",
        "customers": "customers",
        "orders": "orders",
        "products": "products",
    }

    # Sheets we explicitly ignore (not needed for the order model)
    _IGNORED_SHEETS = {"employees", "shippers", "suppliers"}

    def can_handle(self, profile: FileProfile) -> bool:
        return profile.suggested_adapter == self.name

    def plan(self, profile: FileProfile, buf: BytesIO) -> AdapterPlan:
        buf.seek(0)
        try:
            xls = pd.ExcelFile(buf, engine="openpyxl")
        except Exception:
            return AdapterPlan(
                adapter_name=self.name,
                description=self.description,
                profile_family=self.profile_family,
                warnings=["Could not open workbook to build plan."],
            )

        sheet_lower_map = {s.lower(): s for s in xls.sheet_names}
        ignored = [s for s in xls.sheet_names if s.lower() in self._IGNORED_SHEETS]
        extra = [s for s in xls.sheet_names
                 if s.lower() not in self._SHEET_ALIASES and s.lower() not in self._IGNORED_SHEETS]

        mappings = self._detect_mappings(xls, sheet_lower_map)
        assumptions = self._detect_assumptions(xls, sheet_lower_map)

        return AdapterPlan(
            adapter_name=self.name,
            description="Northwind-style order workbook → canonical Order Reporting.",
            profile_family=self.profile_family,
            field_mappings=mappings,
            assumptions=assumptions,
            ignored_sheets=ignored + extra,
            will_produce="Full Order Reporting dataset (adapted from Northwind layout).",
        )

    def transform(self, buf: BytesIO) -> AdapterResult:
        buf.seek(0)
        try:
            xls = pd.ExcelFile(buf, engine="openpyxl")
        except Exception as exc:
            return AdapterResult(
                success=False,
                adapter_name=self.name,
                profile_family=self.profile_family,
                error=f"Could not open workbook: {exc}",
            )

        sheet_lower_map = {s.lower(): s for s in xls.sheet_names}
        warnings: list[str] = []
        plan = self.plan(None, buf)  # type: ignore[arg-type]

        try:
            customers = self._transform_customers(xls, sheet_lower_map, warnings)
            categories = self._transform_categories(xls, sheet_lower_map, warnings)
            products = self._transform_products(xls, sheet_lower_map, warnings)
            orders = self._transform_orders(xls, sheet_lower_map, warnings)
            order_items = self._transform_order_items(xls, sheet_lower_map, warnings)
        except Exception as exc:
            return AdapterResult(
                success=False,
                adapter_name=self.name,
                profile_family=self.profile_family,
                error=f"Transformation failed: {exc}",
                warnings=warnings,
            )

        return AdapterResult(
            success=True,
            adapter_name=self.name,
            profile_family=self.profile_family,
            frames={
                "customers": customers,
                "categories": categories,
                "products": products,
                "orders": orders,
                "order_items": order_items,
            },
            plan=plan,
            warnings=warnings,
        )

    # ── Per-entity transformers ─────────────────────────────

    def _read_sheet(self, xls: pd.ExcelFile, sheet_lower_map: dict, *aliases: str) -> pd.DataFrame:
        """Read a sheet by trying multiple name aliases."""
        for alias in aliases:
            if alias in sheet_lower_map:
                return xls.parse(sheet_lower_map[alias])
        raise KeyError(f"No sheet found for aliases: {aliases}")

    def _transform_customers(self, xls, slm, warnings) -> pd.DataFrame:
        df = self._read_sheet(xls, slm, "customers")
        cols = {c.lower().strip(): c for c in df.columns}

        name_col = _pick(cols, "customername", "companyname", "company_name",
                         "contactname", "contact_name", "name", "customer")
        segment_col = _pick(cols, "segment", "category", "type", "customersegment")
        city_col = _pick(cols, "city", "location", "address")

        result = pd.DataFrame()
        if name_col:
            result["name"] = df[name_col].astype(str).str.strip()
        else:
            # Fallback: use CustomerID or row index
            id_col = _pick(cols, "customerid", "customer_id", "id")
            if id_col:
                result["name"] = df[id_col].astype(str).str.strip()
                warnings.append("No customer name column found; using CustomerID as name.")
            else:
                raise ValueError("Cannot determine customer name column.")

        result["segment"] = df[segment_col].astype(str).str.strip() if segment_col else "General"
        if not segment_col:
            warnings.append("No segment column found; defaulting to 'General'.")

        result["city"] = df[city_col].astype(str).str.strip() if city_col else "Unknown"
        if not city_col:
            warnings.append("No city column found; defaulting to 'Unknown'.")

        return result.drop_duplicates(subset=["name"]).reset_index(drop=True)

    def _transform_categories(self, xls, slm, warnings) -> pd.DataFrame:
        df = self._read_sheet(xls, slm, "categories")
        cols = {c.lower().strip(): c for c in df.columns}

        name_col = _pick(cols, "categoryname", "category_name", "name", "category")
        if not name_col:
            id_col = _pick(cols, "categoryid", "category_id", "id")
            if id_col:
                warnings.append("No category name column; using CategoryID as name.")
                return pd.DataFrame({"name": df[id_col].astype(str).str.strip()}).drop_duplicates()
            raise ValueError("Cannot determine category name column.")

        return pd.DataFrame({
            "name": df[name_col].astype(str).str.strip()
        }).drop_duplicates().reset_index(drop=True)

    def _transform_products(self, xls, slm, warnings) -> pd.DataFrame:
        df = self._read_sheet(xls, slm, "products")
        cols = {c.lower().strip(): c for c in df.columns}

        name_col = _pick(cols, "productname", "product_name", "name", "product")
        cat_col = _pick(cols, "categoryname", "category_name", "category",
                        "categoryid", "category_id")
        price_col = _pick(cols, "unitprice", "unit_price", "price",
                          "unit_price_cents", "unitpricecents")

        if not name_col:
            raise ValueError("Cannot determine product name column.")

        result = pd.DataFrame()
        result["name"] = df[name_col].astype(str).str.strip()

        # Category: resolve ID → name if needed
        if cat_col:
            cat_vals = df[cols[cat_col.lower().strip()] if cat_col.lower().strip() in cols else cat_col]
            if cat_col.lower().strip() in ("categoryid", "category_id"):
                result["category"] = self._resolve_category_id(
                    cat_vals, xls, slm, warnings
                )
            else:
                result["category"] = cat_vals.astype(str).str.strip()
        else:
            result["category"] = "Uncategorized"
            warnings.append("No category column in products; defaulting to 'Uncategorized'.")

        # Price: detect if dollars (float) and convert to cents
        if price_col:
            raw_price = pd.to_numeric(df[cols.get(price_col.lower().strip(), price_col)], errors="coerce").fillna(0)
            if price_col.lower().strip() in ("unit_price_cents", "unitpricecents"):
                result["unit_price_cents"] = raw_price.round(0).astype(int)
            else:
                # Assume dollars → cents
                result["unit_price_cents"] = (raw_price * 100).round(0).astype(int)
                warnings.append("Product prices assumed to be in dollars; converted to cents.")
        else:
            result["unit_price_cents"] = 0
            warnings.append("No price column in products; defaulting to 0.")

        return result.drop_duplicates(subset=["name"]).reset_index(drop=True)

    def _resolve_category_id(self, id_series, xls, slm, warnings) -> pd.Series:
        """Map CategoryID → CategoryName using the categories sheet."""
        try:
            cats = self._read_sheet(xls, slm, "categories")
            cat_cols = {c.lower().strip(): c for c in cats.columns}
            id_col = _pick(cat_cols, "categoryid", "category_id", "id")
            name_col = _pick(cat_cols, "categoryname", "category_name", "name")
            if id_col and name_col:
                lookup = dict(zip(cats[id_col], cats[name_col].astype(str).str.strip()))
                return id_series.map(lookup).fillna("Uncategorized")
        except Exception:
            pass
        warnings.append("Could not resolve CategoryID to name; using ID as category name.")
        return id_series.astype(str)

    def _transform_orders(self, xls, slm, warnings) -> pd.DataFrame:
        df = self._read_sheet(xls, slm, "orders")
        cols = {c.lower().strip(): c for c in df.columns}

        id_col = _pick(cols, "orderid", "order_id", "id")
        cust_col = _pick(cols, "customerid", "customer_id", "customer",
                         "customername", "customer_name")
        date_col = _pick(cols, "orderdate", "order_date", "created_at",
                         "date", "createddate")
        status_col = _pick(cols, "status", "orderstatus", "order_status")

        if not id_col:
            raise ValueError("Cannot determine order ID column.")

        result = pd.DataFrame()
        result["order_id"] = df[id_col].astype(str).str.strip()

        # Customer: resolve ID → name if needed
        if cust_col:
            cust_vals = df[cols.get(cust_col.lower().strip(), cust_col)]
            if cust_col.lower().strip() in ("customerid", "customer_id"):
                result["customer"] = self._resolve_customer_id(
                    cust_vals, xls, slm, warnings
                )
            else:
                result["customer"] = cust_vals.astype(str).str.strip()
        else:
            result["customer"] = "Unknown"
            warnings.append("No customer column in orders; defaulting to 'Unknown'.")

        # Date
        if date_col:
            result["created_at"] = pd.to_datetime(
                df[cols.get(date_col.lower().strip(), date_col)], errors="coerce"
            )
        else:
            result["created_at"] = pd.NaT
            warnings.append("No date column in orders.")

        # Status
        if status_col:
            result["status"] = df[cols.get(status_col.lower().strip(), status_col)].astype(str).str.strip()
        else:
            result["status"] = "completed"
            warnings.append("No status column in orders; defaulting to 'completed'.")

        return result.drop_duplicates(subset=["order_id"]).reset_index(drop=True)

    def _resolve_customer_id(self, id_series, xls, slm, warnings) -> pd.Series:
        """Map CustomerID → customer name using the customers sheet."""
        try:
            custs = self._read_sheet(xls, slm, "customers")
            cust_cols = {c.lower().strip(): c for c in custs.columns}
            id_col = _pick(cust_cols, "customerid", "customer_id", "id")
            name_col = _pick(cust_cols, "customername", "companyname",
                             "company_name", "contactname", "name")
            if id_col and name_col:
                lookup = dict(zip(custs[id_col], custs[name_col].astype(str).str.strip()))
                return id_series.map(lookup).fillna("Unknown")
        except Exception:
            pass
        warnings.append("Could not resolve CustomerID to name; using ID.")
        return id_series.astype(str)

    def _transform_order_items(self, xls, slm, warnings) -> pd.DataFrame:
        df = self._read_sheet(xls, slm, "orderdetails", "ordersdetails",
                              "order_details", "order details")
        cols = {c.lower().strip(): c for c in df.columns}

        oid_col = _pick(cols, "orderid", "order_id", "orderdetailid")
        prod_col = _pick(cols, "productid", "product_id", "product",
                         "productname", "product_name")
        qty_col = _pick(cols, "quantity", "qty", "amount")
        price_col = _pick(cols, "unitprice", "unit_price", "price",
                          "unit_price_cents", "unitpricecents")

        if not oid_col:
            raise ValueError("Cannot determine order ID column in order details.")

        result = pd.DataFrame()
        result["order_id"] = df[oid_col].astype(str).str.strip()

        # Product: resolve ID → name if needed
        if prod_col:
            prod_vals = df[cols.get(prod_col.lower().strip(), prod_col)]
            if prod_col.lower().strip() in ("productid", "product_id"):
                result["product"] = self._resolve_product_id(
                    prod_vals, xls, slm, warnings
                )
            else:
                result["product"] = prod_vals.astype(str).str.strip()
        else:
            result["product"] = "Unknown"
            warnings.append("No product column in order details.")

        # Quantity
        if qty_col:
            result["quantity"] = pd.to_numeric(
                df[cols.get(qty_col.lower().strip(), qty_col)], errors="coerce"
            ).fillna(1).astype(int)
        else:
            result["quantity"] = 1
            warnings.append("No quantity column in order details; defaulting to 1.")

        # Price
        if price_col:
            raw = pd.to_numeric(
                df[cols.get(price_col.lower().strip(), price_col)], errors="coerce"
            ).fillna(0)
            if price_col.lower().strip() in ("unit_price_cents", "unitpricecents"):
                result["unit_price_cents"] = raw.round(0).astype(int)
            else:
                result["unit_price_cents"] = (raw * 100).round(0).astype(int)
                warnings.append("Order item prices assumed to be in dollars; converted to cents.")
        else:
            result["unit_price_cents"] = 0
            warnings.append("No price column in order details; defaulting to 0.")

        return result.reset_index(drop=True)

    def _resolve_product_id(self, id_series, xls, slm, warnings) -> pd.Series:
        """Map ProductID → product name using the products sheet."""
        try:
            prods = self._read_sheet(xls, slm, "products")
            prod_cols = {c.lower().strip(): c for c in prods.columns}
            id_col = _pick(prod_cols, "productid", "product_id", "id")
            name_col = _pick(prod_cols, "productname", "product_name", "name")
            if id_col and name_col:
                lookup = dict(zip(prods[id_col], prods[name_col].astype(str).str.strip()))
                return id_series.map(lookup).fillna("Unknown")
        except Exception:
            pass
        warnings.append("Could not resolve ProductID to name; using ID.")
        return id_series.astype(str)

    # ── Plan helpers ────────────────────────────────────────

    def _detect_mappings(self, xls, slm) -> list[FieldMapping]:
        mappings: list[FieldMapping] = []
        # Sheet-level mappings
        for sheet in xls.sheet_names:
            alias = sheet.lower().strip()
            if alias in self._SHEET_ALIASES and alias != self._SHEET_ALIASES[alias]:
                mappings.append(FieldMapping(
                    source=f"sheet:{sheet}",
                    target=self._SHEET_ALIASES[alias],
                    transform="Sheet renamed to canonical entity.",
                ))

        # Column-level: sample the orders sheet for common renames
        if "orders" in slm:
            df = xls.parse(slm["orders"], nrows=0)
            cols = {c.lower().strip() for c in df.columns}
            if "orderdate" in cols:
                mappings.append(FieldMapping("OrderDate", "created_at", "date column"))
            if "orderid" in cols:
                mappings.append(FieldMapping("OrderID", "order_id"))
            if "customerid" in cols:
                mappings.append(FieldMapping("CustomerID", "customer", "resolved via customers sheet"))

        return mappings

    def _detect_assumptions(self, xls, slm) -> list[str]:
        assumptions: list[str] = []
        if "orders" in slm:
            df = xls.parse(slm["orders"], nrows=0)
            cols = {c.lower().strip() for c in df.columns}
            if "status" not in cols and "orderstatus" not in cols:
                assumptions.append("No status column — all orders will default to 'completed'.")

        # Price assumption
        for sheet_alias in ("products", "orderdetails", "ordersdetails", "order_details"):
            if sheet_alias in slm:
                df = xls.parse(slm[sheet_alias], nrows=0)
                cols = {c.lower().strip() for c in df.columns}
                if "unitprice" in cols or "price" in cols:
                    assumptions.append("Prices assumed to be in dollars; will be converted to cents (×100).")
                    break

        return assumptions


# ── Helpers ─────────────────────────────────────────────────────

def _pick(col_map: dict[str, str], *candidates: str) -> str | None:
    """Return the first matching column name from candidates."""
    for c in candidates:
        if c in col_map:
            return col_map[c]
    return None


# ── Auto-register ───────────────────────────────────────────────

register_adapter(NorthwindOrderAdapter())
