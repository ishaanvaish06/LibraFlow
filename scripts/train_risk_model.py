"""
Regenerate the shipped late-return risk model.

Usage:
    python scripts/train_risk_model.py [output_path]

Writes a joblib-serialised LogisticRegression to
``models/risk_model.joblib`` (default) and prints a train/test accuracy on
the seeded dataset so the change is inspectable. Run this whenever the seed
features or domain rules change.
"""

from __future__ import annotations

import os
import sys

# Allow running as a script from a fresh clone.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from libflow.ai.risk_seed import generate_seed_training_data

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "models" / "risk_model.joblib"


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)

    X, y = generate_seed_training_data(n_samples=1200, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    clf = LogisticRegression(
        max_iter=1000,
        C=1.0,
        class_weight="balanced",
        random_state=42,
    )
    clf.fit(X_train, y_train)

    train_acc = accuracy_score(y_train, clf.predict(X_train))
    test_acc = accuracy_score(y_test, clf.predict(X_test))
    test_prob = clf.predict_proba(X_test)[:, 1]

    joblib.dump({"clf": clf}, output_path)

    print(f"Saved model to {output_path}")
    print(f"Train accuracy: {train_acc:.3f}")
    print(f"Test accuracy:  {test_acc:.3f}")
    print(f"Test prob range: [{test_prob.min():.3f}, {test_prob.max():.3f}]")


if __name__ == "__main__":
    main()