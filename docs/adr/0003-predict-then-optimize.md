# 3. Predict-then-optimize, not embedded ML

Status: accepted

## Context
Embedding a trained model in the MILP only pays off when decisions change the model's inputs. Here
the violation probability p_i does not depend on the schedule within a horizon; the only feedback is
the explicit Harrington state.

## Decision
Fit a regularized, calibrated logistic regression first, then pass p_i to the optimizer as a plain
prize coefficient (Week 4 of the course: predict-then-optimize). Labels are sparse and biased, so
prefer simple models with shrinkage over deep models.

## Consequences
Simple, auditable, easy to maintain. Prediction errors propagate to the schedule, so run sensitivity
analysis on p_i. Smart-predict-optimize and embedding remain stretch ideas.
