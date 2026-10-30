# Sample document

[`docling.pdf`](docling.pdf) is the **Docling Technical Report**, version 1.0,
by Christoph Auer and coauthors at the AI4K Group, IBM Research.

- Source: [arXiv:2408.09869v5](https://arxiv.org/abs/2408.09869v5), revised 9 December 2024.
- License: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/), as linked on the arXiv record.
- Changes: none; the PDF is included unchanged as a sample for ingestion and retrieval.
- Attribution: the paper and its authors are independent of this application;
  inclusion does not imply endorsement.
- SHA-256: `82dd470712ce8389f19f20eb9330475e2166a281f8c7990a9f1d0763d73b4d22`.

The paper's license applies to the PDF separately from the application code.
Docling describes its own features in the paper; this app uses LlamaIndex file
readers and does not install or run Docling.

## First test

Upload the PDF through Streamlit, click **Ingest document**, and wait for indexing.
Then ask one of these questions with three retrieved passages:

| Question | Evidence to look for |
| --- | --- |
| What problem does Docling solve? | Converting PDFs into machine-processable documents (page 1). |
| Which formats can Docling export to? | JSON and Markdown (page 2). |
| Which model does Docling use for table structure recognition? | TableFormer (page 1). |
| Can Docling run locally, and does it support OCR? | Local execution on commodity hardware and optional OCR (pages 1–2). |

These are checks against this version of the paper, not claims about the latest
Docling release. Review the answer's numbered supporting passages rather than
expecting identical wording on every run.

For the Inngest dashboard instead of the UI, copy the PDF into the ignored
`data/` directory first (`mkdir -p data` then `cp examples/docling.pdf data/docling.pdf`
on macOS/Linux). Send this event:

```json
{"name": "rag/ingest_document", "data": {"path": "data/docling.pdf"}}
```

The backend accepts direct file paths only under `data/`; the Streamlit upload
handles that copy for you. Use one ingestion route per test to avoid indexing
the same document under two source paths.
