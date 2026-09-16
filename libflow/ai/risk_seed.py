"""
Seeded training data for ``RiskAssessmentModel``.

Generates a synthetic-but-plausible circulation history dataset in the exact
feature space the model consumes, so the trainer can be re-run deterministically.

Each sample:
    [role_encoded, log1p(total_borrows), late_ratio, damaged_count,
     fines/200, active_ratio] -> whether the borrower later returned late
     (1) or cleanly (0).
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

_ROLE_INDEX = {"STUDENT": 0, "FACULTY": 1, "LIBRARIAN": 2, "ADMIN": 3}

_RN = np.random.RandomState(0)


def _sample_role() -> str:
    return _RN.choice(["STUDENT", "FACULTY", "LIBRARIAN"], p=[0.6, 0.25, 0.15])


def generate_seed_training_data(
    n_samples: int = 800,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.RandomState(random_state)
    rows: list = []
    labels: list = []

    for _ in range(n_samples):
        role = _sample_role()
        role_enc = _ROLE_INDEX[role]

        # Borrow count depends on role.
        if role == "STUDENT":
            total = rng.randint(0, 25)
            max_active = 4
        elif role == "FACULTY":
            total = rng.randint(0, 60)
            max_active = 10
        else:  # LIBRARIAN
            total = rng.randint(0, 20)
            max_active = 15

        # Latent "habit" class: clean vs habitual late returner.
        habit = rng.choice(["clean", "borderline", "habitual"], p=[0.55, 0.25, 0.20])
        if habit == "clean":
            late_ratio = rng.uniform(0.0, 0.05)
            damaged = int(rng.random() < 0.02)
            fines = rng.uniform(0.0, 40.0)
        elif habit == "borderline":
            late_ratio = rng.uniform(0.05, 0.25)
            damaged = int(rng.random() < 0.10)
            fines = rng.uniform(20.0, 120.0)
        else:
            late_ratio = rng.uniform(0.30, 1.0)
            damaged = int(rng.random() < 0.25)
            fines = rng.uniform(80.0, 400.0)

        active = rng.randint(0, max_active + 1)
        active_ratio = active / max_active if max_active else 0.0

        if total == 0:
            # New users: mildly positive default, mostly safe.
            label = int(rng.random() < 0.15)
        else:
            score = late_ratio * 2.0 + damaged * 0.5 + (fines / 200.0)
            label = int(rng.random() < score)

        rows.append([
            float(role_enc),
            float(np.log1p(total)),
            float(late_ratio),
            float(damaged),
            float(fines / 200.0),
            float(min(1.0, active_ratio)),
        ])
        labels.append(label)

    return np.asarray(rows, dtype=float), np.asarray(labels, dtype=int)
