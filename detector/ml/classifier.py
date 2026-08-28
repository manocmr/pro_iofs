from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .dataset import load_training_data

_pipeline = None


def _build_pipeline():
    texts, labels = load_training_data()
    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )
    pipeline.fit(texts, labels)
    return pipeline


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = _build_pipeline()
    return _pipeline


def predict_fraud_probability(text):
    """Retourne la probabilité (0-100) que le message soit frauduleux selon le modèle ML."""
    pipeline = _get_pipeline()
    proba = pipeline.predict_proba([text])[0][1]
    return round(proba * 100)
