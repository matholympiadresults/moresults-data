"""EGMO (European Girls' Mathematical Olympiad) data processing.

Three-stage pipeline:
1. scraper.download_raw() - Downloads raw HTML and CSV files
2. scraper.parse_raw() - Parses raw files into structured JSON
3. ingester.ingest_egmo_data() - Ingests parsed JSON into normalized database
"""
