"""EGMO (European Girls' Mathematical Olympiad) data processing.

Three-stage pipeline:
- download: Downloads raw HTML and CSV files from egmo.org
- parse: Parses raw files into structured JSON
- ingest: Ingests parsed JSON into the normalized database
"""
