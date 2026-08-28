"""Évaluation du classifieur par validation croisée stratifiée.

Le dataset est trop petit pour un split train/test unique fiable (18-30
exemples par classe) : la validation croisée donne une estimation plus
honnête en faisant tourner chaque exemple en test au moins une fois.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline

from .dataset import load_training_data


def evaluate(n_splits=5):
    texts, labels = load_training_data()

    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )

    n_splits = min(n_splits, min(labels.count(0), labels.count(1)))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=0)
    predictions = cross_val_predict(pipeline, texts, labels, cv=cv)

    report = classification_report(
        labels, predictions, target_names=["legitime", "fraude"], output_dict=True
    )
    matrix = confusion_matrix(labels, predictions)

    return {
        "n_samples": len(texts),
        "n_splits": n_splits,
        "report": report,
        "confusion_matrix": matrix.tolist(),
    }


if __name__ == "__main__":
    import json

    result = evaluate()
    print(f"Échantillons : {result['n_samples']} | Folds : {result['n_splits']}")
    print(f"Matrice de confusion [[TN, FP], [FN, TP]] : {result['confusion_matrix']}")
    print(json.dumps(result["report"], indent=2, ensure_ascii=False))
