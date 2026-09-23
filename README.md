# United Brands v Commission: Relevant Product Market Chatbot

A single-document RAG chatbot that answers questions about how the Court of Justice defined the relevant **product** market in *United Brands Co v Commission of the European Communities* (C-27/76) [1978] ECR 207, paragraphs [10]–[35].

Every answer is:

- **source-faithful:** it contains no inferences beyond the judgment;
- **attributed:** each statement is attributed to the applicant, the Commission or the Court;
- **pinpoint-cited:** it uses AGLC paragraph pinpoints, e.g. `[29]`, `[28]–[30]`.

**Deployed app:** [add Streamlit Cloud URL]
**Full write-up:** [`United_Brands_Chatbot_Report.docx`](United_Brands_Chatbot_Report.docx) (design, testing log and known limitations)

---

## How it works

1. **Introduction page** (`home.py`): a five-step walkthrough of the case that leads into the chatbot (it can be skipped).
2. **Chatbot** (`pages/chatbot.py`), which handles each question in five steps:
   1. **Follow-up handling.** A code-level check decides whether the question stands on its own. Only genuine follow-ups ("How did the Court respond to that?") are rewritten by GPT-4o into a standalone search query.
   2. **Retrieval.** The three most similar chunks are retrieved from Chroma (`text-embedding-3-large`).
   3. **Context.** Each chunk is labelled with its speaker, and with an attribution note where one is needed. Paragraph numbers are inside the chunk text.
   4. **Generation.** GPT-4o (temperature 0) writes the answer under a strict source-fidelity prompt.
   5. **Answer check.** Code flags uncited sentences and phrases such as "including" or "therefore"; up to two targeted correction passes fix them.
3. **Shared module** (`shared.py`): the stylesheet, case details and the `aglc_pinpoint()` citation formatter used by both pages.

### Chunking

The judgment is chunked by the **structure of the Court's reasoning**, not by length:

| # | Paragraphs | Speaker | Content |
|---|---|---|---|
| 01 | [10]–[11] | The Court | Why the market must be defined |
| 02 | [12]–[13] | The Court / the applicant | The question; the applicant's argument |
| 03 | [14]–[18] | The applicant | Evidence relied on and the applicant's conclusion |
| 04 | [19]–[21] | The Commission | The Commission's response |
| 05 | [22]–[27] | The Court | Legal test; year-round availability |
| 06 | [28]–[30] | The Court | Cross-elasticity; oranges and apples |
| 07 | [31]–[33] | The Court | Characteristics of the banana; price effects |
| 08 | [34]–[35] | The Court | Conclusion |

## Repository structure

```
├── home.py                     # introduction walkthrough (landing page)
├── pages/
│   └── chatbot.py              # the chatbot
├── shared.py                   # styles, case details, AGLC formatter
├── Chunks - United Brands v Commission - Relevant Product Market/
│   └── 01_… – 08_….txt         # the eight chunks, paragraph-numbered
├── requirements.txt
└── United_Brands_Chatbot_Report.docx
```

## Running locally

```bash
pip install -r requirements.txt
streamlit run home.py
```

The app expects two secrets, set as environment variables in a local `.env` file or in the Streamlit Cloud secrets settings:

```
OPENAI_API_KEY=...
PASSWORD=...
```

Neither is committed to the repository.

## Test case

This test checks a follow-up question in a continuous conversation. The follow-up contains no subject of its own, so it depends on the rewriting step.

**Question 1:** *What evidence did the applicant rely on regarding apples?*

> The applicant relied on studies carried out by the Food and Agriculture Organization (FAO), which confirm that the price of apples has a statistically appreciable impact on the consumption of bananas in the Federal Republic of Germany [15].

**Question 2 (follow-up):** *And what did the Court find?*

Searched for: *What did the Court find regarding the impact of apple prices on the consumption of bananas?*

> The Court found that, as far as concerns apples, there is only a relative degree of substitutability between apples and bananas [29]. The Court noted that this small degree of substitutability is accounted for by the specific features of the banana and all the factors which influence consumer choice [30].

**Expected behaviour:**

- The follow-up is rewritten to name apples.
- Chunk [28]–[30] is retrieved.
- The answer cites [29] and [30] individually, keeps "only a relative degree", and attributes every sentence to the Court.

The full test log is in the report (section 11).

## Artefacts

- `United_Brands_Chatbot_Report.docx`: design rationale, full testing log, known limitations and the final system prompt
- `Chunks - …/`: the eight source chunks used for retrieval
- Screenshots of the test runs: [add folder or link]
