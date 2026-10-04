# "Census floor" and "second pass", in plain language

For collaborators who have not read the memos. No code or statistics needed. The technical version is in [memo 06](process/06_Regime_Comparison.md) and [ADR 0007](adr/0007-two-implementations-one-regime.md).

## The one-paragraph version

Today, inspectors can only afford to check about four stores a month, so we pick the stores most likely to be selling to minors and check those. A **census floor** changes the promise: **every tobacco store in the city gets checked once in the year**, no exceptions. The "floor" is the minimum anyone can expect: nobody falls below one check. A **second pass** is what we do with the checks left over afterward: **go back to some stores for another look, choosing them based on what the first round showed us.** Need still matters, but it now decides *when* a store is checked and *whether it is checked again*. It no longer decides whether a store is checked at all.

## The two terms, defined

**Census floor.** One undercover check at every retail location, spread over about nine months, on dates the store cannot predict. The riskiest stores go earlier in that window. "Census" means we count everyone rather than sampling. "Floor" means this is the least any store gets; it is not a ceiling.

**Second pass.** After the census floor, a smaller set of repeat checks (about a quarter as many as the first round). Stores are picked using three things: how risky the model thinks they are, what the first check found, and a deliberate dash of randomness so the list is not guessable. It exists because the first pass tells us something we did not know, and we should use it.

**Budget-capped plan (today's design, for contrast).** Check roughly the 4 highest-need stores a month, plus a random share, and stop when the money runs out. About 86% of stores go unchecked in a given year.

## What each person knows, believes and does

The idea of the regime is easiest to see through the eyes of the people inside it.

### The store owner or clerk

| | Budget-capped | Census floor + second pass |
|---|---|---|
| **What they can know** | Almost nothing. Most stores are never checked, and a check on a neighbor says little about their own odds. | "Every store in the city gets checked this year. It will happen to me." |
| **What they likely think** | "It probably won't be me" for most stores, and "they always come to us" for stores that were picked before. | "I cannot opt out of being looked at, so checking ID every time is the safe habit." |
| **What the design is trying to do** | Concentrate pressure where harm is likeliest, and keep some randomness so no one is sure. | Make being checked a certainty, not a gamble, and keep the *timing* unpredictable. |
| **What it does not tell them** | Which day or hour. (Same for both.) | Which day or hour. (Same for both.) Nobody is told the schedule. |

We do not know how much a visible, certain check changes seller behavior. That is the key unknown (see "What we do not know" below). The census floor is a bet that certainty is a stronger signal than occasional picks, not something we have measured.

### The inspector and the underage purchaser team

- **Under the cap:** the work is a short, ranked list. Little routing to do, because stores are spread out and checks are few.
- **Under the census floor:** a real scheduling job, with about 345 stores to cover over roughly nine months. They need to see the list as fair and sensible. It must be explainable ("every store, riskiest first") rather than a mystery pick.
- **Under both:** one purchase attempt is close to a coin flip. A clean result means "this attempt did not catch a sale," not "this store is compliant."

### The Department of Health (the decision-makers)

- They see a funding tradeoff: roughly $27,000 for the census floor (base case) against about $3,300 for today's volume. See [memo 06](process/06_Regime_Comparison.md) section 3.2.
- They also see a *defensibility* question: "Why was my store checked and that one wasn't?" The census floor's answer is simple and fair: everyone was. The capped plan's answer is a risk score, which is harder to explain and has to be audited for fairness (poverty and race; see below).
- They should not read the census floor as "the efficient option." It is not cheaper per violation found.

### The FDA and the public

- FDA wants repeat violators handled and escalated. A second pass can do that, though re-checking known violators finds almost no *new* violators. The choice of rule follows the goal.
- The public sees a regime that treats every neighborhood the same way in the first pass. Fairness is built into the design, and we still check the outcome (below).

## What the second pass is, and is not

**It is** a way to learn. After round one, we know which stores sold and which did not. The second pass uses that, together with the model's prior opinion, to decide where another check is worth the most.

**It is not**
- A punishment list. Nobody is added because they were caught; the pick weighs several things and includes randomness.
- A guarantee of a re-check. A store that passed round one may never be seen again that year.
- Proof that a store is clean. One passed check is one passed attempt.

The way second-pass stores are chosen is called a "Thompson" draw in the technical docs. In plain terms: stores that look riskier get more chances to be picked, but not a certainty, and stores we know little about get a fair shot too. It keeps the list unpredictable.

## Common misunderstandings

| What someone might hear | What it actually means |
|---|---|
| "A census catches more violations." | No. Per check it catches no more than targeting and a bit less. What it buys is coverage, an unbiased reading on every store, and a clean estimate of the city's overall rate. |
| "Census means no priorities." | No. Priority decides order and repeats. It does not decide inclusion. |
| "Floor means a cap." | The opposite. It is the minimum. |
| "Every store gets checked twice." | No. Everyone once. Only a chosen subset gets a second look. |
| "This reduces underage sales." | Not shown. It is plausible, and it depends on how sellers respond to being visible. That is the main thing a pilot would measure. |
| "Equal treatment means equal outcomes." | Equal first-pass coverage, yes. We still check who is landing in the *second* pass and whether majority-minority or high-poverty tracts are over-checked per store. |

## Does the regime treat neighborhoods fairly? (what we checked)

Store scoring does not use race or income. We audit the *outcome* anyway, because store type and school proximity can track neighborhoods.

- **Poverty:** neither regime sends a disproportionate share of checks to the highest-poverty quartile (capped 26.0%, census 22.4%, against 21.7% of stores).
- **Race and ethnicity** (tracts where over half of residents are not non-Hispanic White; 25.2% of stores): the capped plan sends 32.2% of expected checks there (1.39 times the per-store rate of other tracts). The census floor sends 26.6% (1.07 times). So the census floor is the more even design.
- The 12-visit schedule actually drawn for this plan puts 20.0% of visits in those tracts. With so few visits this is not evidence either way.

Margins of error on neighborhood data are wide, so read these as direction, not decimals.

## What we do not know

1. **Does being visible reduce underage sales?** No data yet. This single unknown decides whether the census floor is worth its cost (the break-even is in memo 06).
2. **Do stores differ in ways our model misses?** If not, the model's own ranking is as good as the second pass. If so, the second pass pays off.
3. **Real unit costs and authority.** The dollar figures are bottom-up assumptions until DOH confirms them.

These are why the recommendation is a **one-year learning pilot** (census floor, randomized timing, randomized second pass), not an immediate switch.

## Quick reference

| Term | Say it as |
|---|---|
| Census floor | "Every store, once, at a time it can't predict. That is the minimum anyone gets." |
| Second pass | "Another look at some stores, chosen using what round one showed us." |
| Budget-capped | "Only as many checks as the budget allows, highest need first." |
| Majority-minority tract | "A neighborhood where more than half of residents are not non-Hispanic White." |
| Learning pilot | "Run the census floor for a year, randomized, so we can measure what it does before deciding." |

*Numbers are from `outputs/regime_equity.csv`, `outputs/regime_frontier.csv` and memo 06; assumptions (nine-month floor, second pass at 25% of checks) are in `config/default.yaml`.*
