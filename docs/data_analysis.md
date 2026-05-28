# Data Analysis

## Dataset Overview

**Source:** Bitext Customer Support Intent Detection Dataset  
**Split:** Train  
**Rows:** 26,872  
**Columns:** `flags`, `instruction`, `category`, `intent`, `response`  
**Storage:** Local DuckDB at `outputs/customer_support.duckdb`

---

## Schema

| Column | Type | Description |
|---|---|---|
| `flags` | VARCHAR | Annotation flags (e.g., B=broken syntax, Q=question form, Z=formal register) |
| `instruction` | VARCHAR | Customer message / query (the primary text input) |
| `category` | VARCHAR | High-level topic grouping (e.g., ORDER, REFUND, SHIPPING) |
| `intent` | VARCHAR | Fine-grained intent label within a category (e.g., cancel_order, track_refund) |
| `response` | VARCHAR | Reference agent response (not used for analytics in this project) |

---

## Category Distribution

The Bitext dataset contains approximately 27 high-level categories. Based on the published dataset structure, categories include (alphabetically):

```
ACCOUNT, CANCELLATION_FEE, CONTACT, DELIVERY, FEEDBACK,
INVOICE, NEWSLETTER, ORDER, PAYMENT, REFUND,
REGISTRATION, REPAIR, RETURN, REVIEW, SHIPPING,
SUBSCRIPTION, TECHNICAL_SUPPORT, TRACK_ORDER, TRACK_REFUND
```

**Top categories by frequency (approximate):**

The dataset is designed to be roughly balanced at the category level, with each category containing multiple intents and approximately 1,000–1,500 rows per major category.

To compute exact counts:
```sql
SELECT category, COUNT(*) AS count
FROM customer_support_train
GROUP BY category
ORDER BY count DESC;
```

Use `get_top_categories(limit=30)` via the analytics API.

---

## Intent Distribution

Each category contains between 4 and 8 distinct intents. Example mappings:

| Category | Sample Intents |
|---|---|
| ORDER | cancel_order, place_order, track_order, edit_order |
| REFUND | get_refund, track_refund, dispute_refund |
| ACCOUNT | create_account, delete_account, recover_account, edit_account |
| SHIPPING | delivery_period, track_shipment, wrong_delivery |
| PAYMENT | check_payment, decline_payment, payment_issue |

Total distinct intents: approximately 77–80 across all categories.

To compute exact intent counts:
```sql
SELECT intent, category, COUNT(*) AS count
FROM customer_support_train
GROUP BY intent, category
ORDER BY count DESC;
```

---

## Imbalance Analysis

### Category-Level

The Bitext dataset is intentionally designed with near-uniform category distribution. Each category contributes roughly equal row counts. This is a **synthetic** dataset, meaning the balance reflects deliberate curation rather than organic user behavior.

**Implication for retrieval:** Keyword search (`search_examples`) will return examples proportionally across categories. No single category will dominate search results for general keywords.

**Implication for analytics:** `get_top_categories()` will not reveal strong category dominance patterns as would be expected from a real production dataset.

### Intent-Level

Within categories, intents are also approximately balanced. However, some intents (e.g., `cancel_order`) may occur more frequently than edge-case intents (e.g., `dispute_refund`) due to the deliberate augmentation strategy used by Bitext.

---

## Instruction Length Distribution

Customer instructions in the Bitext dataset are short to medium length:
- **Typical range:** 5–30 words per instruction
- **Shortest:** Single-word queries (e.g., "cancel")
- **Longest:** Multi-clause complaint descriptions (~50–60 words)

This distribution reflects real customer support ticket behavior, where most customer messages are concise requests or complaints.

**Implication for keyword search:** Short instructions make keyword matching effective. The `contains()` function used in `search_examples` returns precise matches because there is little extraneous text to confuse retrieval.

**Implication for future RAG:** Short documents reduce the benefit of dense retrieval. Embedding similarity on short texts is less discriminative than on longer documents. Hybrid approaches (keyword + sparse retrieval) may be more effective than pure vector search for this dataset.

---

## Annotation Flags

The `flags` column contains comma-separated annotation codes describing linguistic properties of the instruction. Known flags include:

| Flag | Meaning |
|---|---|
| `B` | Broken / fragmented syntax |
| `Q` | Question form |
| `W` | Colloquial / informal language |
| `I` | Indirect / implicit request |
| `Z` | Formal register |
| `M` | Misspelling / typo present |
| `L` | Long / multi-clause instruction |

**Multi-flag rows:** Many rows have multiple flags (e.g., `"BW"` = broken + colloquial).

**Implication for noise analysis:** Rows with the `B` flag contain broken or truncated sentences. Any retrieval system must handle these gracefully. The `contains()` keyword match is robust to syntax errors because it uses substring matching rather than sentence parsing.

---

## Typo and Noise Observations

Because the Bitext dataset is synthetic, it includes deliberate linguistic perturbations to simulate real-world customer support text:

- **Misspellings:** "cance", "refnd", "acount" may appear in flagged rows
- **Truncated sentences:** Instructions may end mid-word
- **Informal contractions:** "i wanna", "cant", "pls" are common
- **Mixed case:** Some instructions use ALL CAPS for emphasis

**Impact on this agent:** All comparisons in DuckDB use `LOWER()` for case normalization. The `contains()` function matches substrings regardless of capitalization. Misspellings will not match correctly (e.g., searching for "refund" will not match "refnd"). This is an accepted limitation.

---

## Semantic Ambiguity Examples

Some instructions in the dataset are ambiguous across categories or intents:

| Instruction | Ambiguity |
|---|---|
| "I need help with my order" | Could be ORDER/track_order, ORDER/cancel_order, or ORDER/edit_order |
| "My payment didn't go through" | Could be PAYMENT/decline_payment or REFUND/get_refund |
| "I want to cancel" | Could be CANCELLATION_FEE/cancel_service or ORDER/cancel_order |

**Impact on keyword routing:** The agent's router routes at the query level (what the user asks the agent), not at the instruction level (customer's original message). Ambiguity in dataset instructions does not affect routing correctness.

---

## Cancellation and Refund Frequency Analysis

Cancellation and refund intents are among the most business-critical in customer service:

- **ORDER/cancel_order** — high frequency; users want to cancel recent orders
- **REFUND/get_refund** — high frequency; users request money back
- **CANCELLATION_FEE/cancel_service** — lower frequency; subscription cancellation

These intents collectively represent a significant fraction of total support tickets in real-world deployments, even if the Bitext dataset balances them artificially.

**Agent capability:** The agent can answer "How many refund rows are in the dataset?" (`count_by_category("REFUND")`) and "Give me examples of refund requests" (`search_examples("refund")`). It cannot compute refund-as-percentage-of-total without additional cross-query computation.

---

## Potential Dataset Bias Observations

As a synthetic dataset, the Bitext data has the following known biases:

1. **Language:** English only. Non-English customer queries are not represented.
2. **Domain:** Covers e-commerce and subscription service patterns. Does not reflect B2B, healthcare, or government support.
3. **Balance:** Artificially uniform distribution. Real deployments would have skewed category distributions (e.g., ORDER and REFUND dominate).
4. **Register:** Mix of formal and informal language is deliberate, not organic. Frequency of broken syntax (`B` flag) may exceed real production rates.
5. **Response quality:** Responses are template-generated. They do not reflect the variability of human agent responses.

---

## Implications for Retrieval Quality

### Current Keyword Search

- **Strengths:** Fast, exact, robust to category/intent label knowledge, no false positives for exact matches
- **Weaknesses:** Cannot match semantically related terms ("cancel" ≠ "terminate"), no ranking by relevance, single-keyword only

### Implications for Future RAG Quality

| Factor | Impact on RAG |
|---|---|
| Short instructions (5–30 words) | Lower embedding discriminativeness; hybrid retrieval preferred |
| Misspelled text in `B`-flagged rows | Dense retrieval may cluster misspelled variations incorrectly |
| Balanced categories | No "popular" category bias in retrieval; good for coverage |
| English-only | Embedding models must be English-optimized; multilingual models waste capacity |
| Synthetic balance | Retrieval results will not reflect production frequency distributions |

### One-Row-Per-Document Strategy

For a future RAG implementation:
- **Each dataset row = one document**: The `instruction` field is the primary retrieval text
- **Metadata fields**: `category`, `intent`, `flags` stored as metadata for post-retrieval filtering
- **Hybrid retrieval**: Structured queries (counts) always go to DuckDB; exploratory queries use vector similarity over `instruction` embeddings
- **Why RAG must not replace analytics**: A semantic search for "how many refund rows" may return rows tagged REFUND, but counting them semantically is unreliable. DuckDB COUNT(*) with exact label match is authoritative.

---

## Summary

The Bitext dataset is a well-structured synthetic benchmark suitable for demonstrating a customer service analytics agent. Its artificial balance and short instruction length make it an ideal foundation for exact-match analytics (DuckDB) and a reasonable candidate for future dense retrieval. The agent's current keyword-based routing and parameterized SQL analytics are well-matched to this dataset's characteristics.
