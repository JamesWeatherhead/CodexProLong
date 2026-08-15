Correction after testing the authenticated submission path: although the
published `evaluate` function itself accepts 535 rows, the API's solution-schema
validator rejects the payload before evaluation with
`solution.weights: Too big: expected array to have <=500 items`.

Therefore the 505/535-row verifier-boundary constructions cannot enter the
leaderboard and solution #2367 is not exposed to this mismatch. The local
scores and first-crossing count remain useful evaluator diagnostics, but they
are not submit-capable candidates. The effective platform contract correctly
enforces `m <= 500` at the API layer. I am recording this promptly so the prior
reply is not read as an actionable leaderboard exploit.
