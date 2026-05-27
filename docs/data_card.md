# Data Card — Bitext Customer Support Dataset

## Source
Hugging Face:
bitext/Bitext-customer-support-llm-chatbot-training-dataset

## Purpose
Used as the structured analytics source for a deterministic customer-service AI agent.

## Dataset Structure
Columns:
- flags
- instruction
- category
- intent
- response

## Dataset Size
- train split: 26,872 rows

## Engineering Usage
The dataset is persisted locally in DuckDB and queried through deterministic analytics tools.

## Observations
- Synthetic customer-support dataset
- Contains templated placeholders such as {{Order Number}}
- Suitable for analytics and summarization tasks

## Limitations
- Synthetic data only
- No timestamps or user identities
- No conversation history