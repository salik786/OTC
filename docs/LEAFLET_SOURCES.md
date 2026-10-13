# Leaflet sources (seed corpus)

The leaflets in `backend/seed_corpus/` replace the earlier placeholders. They are real, published
patient information leaflets, regrouped under section headers the ingest chunker recognises so
retrieval returns the right section. Wording is verbatim except where noted.

## Paracetamol 500mg Tablets - `paracetamol_leaflet.txt`
- Source: Boots Paracetamol 500mg Tablets (General Sales List, PL 08977/0001), package leaflet last
  revised September 2025. Published on emc: https://www.medicines.org.uk/emc/product/8087/pil
- Edits: regrouped under section headers; brand name removed from the title; "°C" written as
  "degrees C"; emc page chrome and the contact/company footer dropped.

## Daily Multivitamin - `multivitamin_leaflet.txt`
- Source: "Multivitamins & Minerals Tablets" patient information leaflet (generic, over-the-counter
  health supplement): https://irp-cdn.multiscreensite.com/59649488/files/uploaded/HH_SUPPLEMENTS_PIL_Multivitamins-Minerals.pdf
- Edits: regrouped under section headers; the product's all-caps name replaced by "this product";
  decimal commas written as points; the garbled per-ingredient benefits table, regulatory banner and
  manufacturer/registration block dropped.
- Note: this is a South African-registered leaflet. Swap it via the admin panel if the study needs a
  region-specific one.

## Previously uploaded to production (replaced)
Production held `pil.5164.pdf` (Zentiva paracetamol) and a US "One Daily Multi Vitamin" label.
Replacing a leaflet deletes the old document and its chunks, so `retrieved_chunk_ids` on turns
logged before the swap no longer resolve to text.
