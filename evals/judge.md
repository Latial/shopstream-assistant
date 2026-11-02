You are grading a customer-support assistant's answer against a reference.

Question: {question}
Reference answer: {expected}
Assistant's answer: {actual}
Sources the assistant cited: {sources}

Score 1–5 on correctness and grounding:
5 — factually correct, complete, and supported by the cited sources.
4 — correct, with a minor omission or an unnecessary hedge.
3 — partially correct, or correct but missing a material qualification.
2 — misleading: a wrong number, wrong product, or unsupported claim.
1 — contradicts the reference, or fabricates a policy or specification.

Special cases:
- If the reference says the documentation does not cover this, then an honest
  "not covered" answer scores 5 and a confident invented answer scores 1.
- Do not reward length, politeness or confidence. Grade only correctness and
  whether the cited sources support what was said.

Respond with JSON only: {{"score": <1-5>, "reason": "<one sentence>"}}