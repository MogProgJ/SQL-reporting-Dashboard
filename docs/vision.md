# Product Vision

## What this is

SQL Reporting Dashboard is a small, self-contained reporting tool that turns a
normalised PostgreSQL dataset into decision-friendly metrics: KPIs, trends,
filters, drilldowns, and exports. It runs locally with Docker and Streamlit.

## Who it is for

- **Portfolio reviewers** — demonstrates SQL proficiency, data modelling, and
  clean Python architecture without framework bloat.
- **Developers learning reporting patterns** — a readable reference for
  parameterized queries, filter composition, and lightweight dashboarding.
- **Anyone who needs a quick local reporting prototype** — swap the seed data
  for your own tables and the dashboard adapts.

## Core product promise

> Give a user a seeded database and a single command, and they get a working
> reporting dashboard with filters, KPIs, charts, drilldowns, anomaly
> surfacing, and CSV export — no accounts, no deploy, no config ceremony.

## What "good" looks like

- **Fast to run.** `docker compose up -d`, seed, `streamlit run app.py`. Under
  two minutes from clone to dashboard.
- **Honest data.** Every number traces back to a parameterized SQL query against
  a real schema. No fake aggregations or hard-coded metrics.
- **Readable code.** A new contributor can understand the full stack (schema →
  queries → UI) in one sitting.
- **Portfolio-strong.** Clean enough to show in an interview. Demonstrates SQL,
  Python, data modelling, and product thinking.

## What this is NOT

- Not a BI platform. No multi-tenant workspaces, no drag-and-drop report
  builder, no scheduled delivery.
- Not a SaaS product. No auth, no user accounts, no billing.
- Not an enterprise data pipeline. No Airflow, no dbt, no data lake.
- Not an AI/ML project. Anomaly surfacing uses transparent statistical rules,
  not black-box models.
- Not a front-end showcase. Streamlit handles the UI; the value is in the data
  layer and the SQL.
