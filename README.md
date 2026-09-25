# United Brands v Commission — Relevant Product Market Chatbot

A retrieval-augmented generation (RAG) chatbot that answers questions about
how the Court of Justice defined the **relevant product market** in
*United Brands Co. v Commission* (Case 27/76, 14 February 1978),
paragraphs [10]–[35].

**Deployed app:** https://assessment1-qtirjfzqthzqe32n698ajh.streamlit.app/

**Password:** Bananas123

LAWS90286 — Assignment 1

---

## What the app does

The app has two pages:

- **Introduction:** a short, step-by-step introduction to the case (the
  background, the market-definition question, the parties' positions,
  the Court's test and its answer), with a small guessing question and
  a downloadable PDF summary. Every statement about the judgment is
  cited to its paragraph.
- **Chatbot:** answers questions about paragraphs [10]–[35] of the
  judgment. Every sentence that reports the judgment ends with an AGLC
  pinpoint citation (e.g. [29]). Hovering over (or tapping) a citation
  shows the text of the cited paragraph, and the **Sources** expander
  under each answer shows the passages the answer was based on.

Three starter questions help new users begin, and each introduction step
has an "Ask the chatbot about this" button that opens the chatbot with a
suggested question. The sidebar links back to the introduction, resets
the conversation, and opens the full text of [10]–[35] ("Read the
judgment"), with the original report pages as a PDF and a link to the
full judgment on EUR-Lex.

## The document

- **Source:** *United Brands Co. v Commission* (Case 27/76) [1978] ECR
  207, publicly available on EUR-Lex:
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:61976CJ0027
- **Excerpt used:** Chapter I, Section 1 ("The relevant market"),
  paragraphs [10]–[35]

## How it works

### 1. Chunking

The excerpt was split by hand into **eight chunks, one per step of the
Court's reasoning**:

| Chunk | Paragraphs | Content | Speaker |
|---|---|---|---|
| 01 | [10]–[11] | How the relevant market must be defined | Court |
| 02 | [12]–[13] | The question; the applicant's argument | Court / applicant |
| 03 | [14]–[18] | The applicant's seasonal evidence and conclusion | Applicant |
| 04 | [19]–[21] | The Commission's response | Commission |
| 05 | [22]–[27] | The Court's test; year-round supply | Court |
| 06 | [28]–[30] | Cross-elasticity; oranges and apples | Court |
| 07 | [31]–[33] | The banana's characteristics; price effects | Court |
| 08 | [34]–[35] | The Court's conclusion | Court |

Chunking by reasoning step means that each chunk has one function and
(mostly) one speaker, and that the judgment's back-references ("these
studies" [16], "this particular feature" [25], "this small degree of
substitutability" [30], "all these considerations" [34]) stay in the
same chunk as the paragraphs they refer to.

Each chunk carries metadata: its paragraph range, its speaker, and,
where a chunk mixes voices or contains a party's evidence, a short
attribution note (e.g. that [14]–[17] are evidence relied on by the
applicant, not findings of the Court).

### 2. Vector database and retrieval

The judgment text is stored in **ChromaDB** at two levels, in two
collections, both embedded with OpenAI's `text-embedding-3-large`:

| Collection | Contents | Good at |
|---|---|---|
| `united_brands_chunks` | the 8 chunks, one per reasoning step | questions about a step as a whole (e.g. "Did the Court find that bananas form a market of their own?") |
| `united_brands_paragraphs` | the 26 paragraphs [10]–[35], each tagged with its chunk | questions about a single point (e.g. apples, which appear in one clause of [15]) |

For each question, retrieval runs in four steps:

1. **Query rewriting (follow-ups only).** A follow-up such as "And
   apples?" or "Why?" can't be searched on its own, so the model
   rewrites it into a standalone query ("What did the Court find about
   apples?"). It replaces only the words that point back to the
   conversation and adds no terms from earlier answers, because such
   terms belong to one party's reasoning and pull the search towards
   that party. Standalone questions are searched exactly as typed.

2. **Two semantic searches.** The query is embedded and compared by
   vector similarity against both collections:
   - the **chunk search** ranks the 8 chunks directly;
   - the **paragraph search** ranks the 26 paragraphs, and each chunk
     takes the position of its best-matching paragraph.

   This gives two rankings of the same 8 chunks.

3. **Merging the rankings (reciprocal rank fusion).** Each chunk scores
   1 / (60 + its position) in each ranking, and the two scores are
   added (Cormack, Clarke & Büttcher, 2009). A chunk that ranks near
   the top in *either* search therefore rises in the combined ranking.
   RRF uses only positions, not raw similarity scores, so the two
   searches don't need to be on the same scale.

4. **Returning whole chunks (small-to-big).** The three highest-ranked
   chunks are passed to the model **in full**, even when a single
   paragraph found them. So the model always reads a paragraph together
   with the rest of its reasoning step, including the paragraphs its
   back-references point to. 

**Why two levels?** In testing, each level on its own failed different
questions. Whole-chunk search missed points made in a single clause
(apples in [15]), because the rest of the chunk dilutes them.
Paragraph search missed short conclusion paragraphs ([35]:
"Consequently the banana market is…"), because they carry little
content of their own. Searching at both levels and merging the results
fixed both kinds of question, while the model still reads whole
reasoning steps. (See *Approaches tested and rejected* below.)

### 3. Answering

The model (`gpt-4o`, temperature 0) answers only from the retrieved
chunks. The system prompt contains general rules for reporting a
judgment, none of them specific to this case:

- report only what the paragraphs say, and cite every sentence;
- keep qualifiers ("only", "very", "even", "sufficiently") and lists
  exactly as the paragraph gives them;
- open every sentence by naming its source (the applicant, the
  Commission, the Court, or a piece of evidence);
- treat a statement of what must be shown ("for X to be …, it must be
  possible …") as a legal test, not a finding;
- correct a question built on a false premise, citing the paragraph
  that states the actual position;
- never infer from a missing passage that the Court did not decide
  something, because the model only sees the retrieved passages;
- for questions outside the product market, report only what the
  retrieved paragraphs say and state that the rest is outside the
  chatbot's scope.

### 4. Answer check

A rule-based check then looks for sentences without a citation,
sentences that don't name their source, and flagged connectors or list
words ("therefore", "including", "however", "indicating", …) that the
retrieved paragraphs don't use themselves. Problems it finds are sent
back to the model for up to two correction passes.

## Design trade-offs

### Speed versus accuracy

Answers take a few seconds. This is a deliberate trade-off in favour of
accuracy: each question can involve several steps, each of which adds
time:

- a model call to rewrite follow-up questions into standalone searches;
- two vector searches (chunks and paragraphs) instead of one;
- the answer itself;
- up to two correction passes, when the answer check finds uncited
  sentences, sentences that don't name their source, or flagged
  wording.

For a legal research tool, an answer that is correctly cited and
attributed was judged more valuable than a faster one.

### Answer length follows the question

The chatbot has no fixed answer length. A broad question 
gets a detailed answer that walks through the
Court's reasoning paragraph by paragraph, while a narrow one 
 gets a single cited sentence. 

## Development and testing

The chatbot was tested in several rounds with about 30 questions
covering: the starter questions, retrieval of specific paragraphs,
questions spanning several chunks, attribution traps, follow-up
questions, false premises and out-of-scope questions. The design
changes below were each made in response to a failure found in
testing, and checked against the same questions afterwards.

### Approaches tested and rejected

- **Whole-chunk search only (original version):** missed the Court's
  conclusion ([34]–[35]) for several questions, because conclusion
  paragraphs carry little content of their own for an embedding to match.
- **Paragraph search only:** found single points better but lost questions that match a reasoning step as a whole.
  Combining both levels kept the gains of each.
- **HyDE (Hypothetical Document Embeddings; Gao et al., 2022):** before
  searching, the model wrote a hypothetical answer, which was searched
  alongside the question. It fixed one question but broke two others,
  and its effect varied between runs of the same question. Its
  hypothetical answers also reflected the model's general knowledge of
  this well-known case, concentrated on one part of the reasoning (the
  banana's characteristics), and included details that are not in the
  judgment (e.g. "ease of digestion"). Because it made retrieval less
  stable and added a model call per question, **HyDE was removed**.
- **Retrieving four chunks instead of three:** not adopted, because it
  would pass half the excerpt to the model with every question, and
  most remaining errors occur inside the retrieved text rather than in
  retrieval.

## Known limitations
- **Retrieval depends on wording.** A question phrased like the
  judgment's framing ("What did the Court decide about the relevant
  product market?") can match the paragraphs that *pose* the question
  ([11]–[12]) instead of the one that *answers* it ([35]). Rephrasing
  ("Did the Court find that bananas form a market of their own?")
  retrieves the conclusion reliably, so that wording is used for the
  starter question. Ambiguous questions ("What did the Court test?")
  may retrieve a different part of the reasoning than intended.
- **Some answers need more than three chunks.** A question such as how
  the Court dealt with the applicant's seasonal evidence draws on
  [26]–[28] and [32]–[33], and the link is implicit in the judgment.
  The chatbot answers such questions only partly.
- **A retrieval miss can look like the judgment's silence.** The model
  only sees the retrieved passages. It is instructed to describe gaps
  as limits of the retrieved passages, not of the judgment, and to
  point the user to the full text.
- **Questions partly outside the scope** (e.g. the geographic market)
  are answered from the paragraphs that touch on them ([10]–[11]),
  without always stating that the rest is out of scope.
- **Fidelity slips remain.** Answers still sometimes drop a qualifier
  ("even", "sufficiently"), attribute what studies show to the Court,
  restate the [22] test as a finding, cite a neighbouring paragraph, or
  link two findings with a word the judgment doesn't use (e.g.
  "showing"). Every sentence is cited and the citation labels show the
  paragraph text, so each statement can be checked against the source.
- **Answers vary slightly between runs,** even at temperature 0, and
  depending on the earlier conversation. The test case below should
  therefore be run in fresh conversations.

---

## Test case
### 1. Correcting a false premise
**Ask:** Why did the Court agree that bananas are part of the fresh
fruit market?

**Expected:** The chatbot points out that the premise is wrong: the
Court did not agree, but found that the banana market is sufficiently
distinct from the other fresh fruit markets [35]. It reports the
supporting findings, e.g. that consumers with a constant need for
bananas are not noticeably enticed away by other fresh fruit [34]. The
Sources include [34]–[35].

*Shows:* the chatbot corrects the question instead of inventing
reasons to support it.

### 2. Telling the parties apart
**Ask:** Who said bananas are a very important part of the diet of
certain sections of the community?

**Expected:** The Commission [19], not the Court, even though the
Court's similar statement about "the very young, the old and the sick"
[31] may also be retrieved.

*Shows:* each statement is attributed to the right speaker.

### 3. Close reporting of the legal framework
**Ask:** What did the Court say about how the relevant market must be
defined?

**Expected:** The market must be defined from the standpoint of the
product and from the geographic point of view [10], with regard to the
particular features of the product and a clearly defined geographic
area where the conditions of competition are sufficiently homogeneous
[11]. Every sentence is cited.

*Shows:* close paraphrase with AGLC pinpoint citations.

### 4. Follow-up questions (one conversation, no reset in between)
**Ask, in order:**
1. What did the Court find about oranges?
2. And apples?
3. Why?

**Expected:**
1. Oranges are not interchangeable with bananas [29].
2. There is only a relative degree of substitutability between bananas
   and apples [29]. 
3. The reason the Court itself gives: the specific features of the
   banana and all the factors which influence consumer choice [30].

*Shows:* follow-ups are rewritten into standalone searches, and "why"
answers give only reasons the judgment itself states.

### 5. Staying within the document
**Ask:** What is the SSNIP test and did the Court apply it?

**Expected:** The chatbot says that the passages retrieved for the
question don't address it and that it covers only the relevant product
market, and does not explain the SSNIP test from general knowledge.

*Shows:* answers are grounded in the judgment only.

## Credits - Built with Streamlit, ChromaDB and the OpenAI API. - [TUTORIAL / CLASS CODE CREDIT] - The selection, chunking and attribution of the judgment text are my own work. Generative AI (Claude) was used to help write and test the code. - Reciprocal rank fusion: G. V. Cormack, C. L. A. Clarke and S. Büttcher, "Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods" (SIGIR 2009). - HyDE: L. Gao, X. Ma, J. Lin and J. Callan, "Precise Zero-Shot Dense Retrieval without Relevance Labels" (2022).
