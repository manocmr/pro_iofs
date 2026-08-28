import re

URL_PATTERN = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)

KNOWN_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "ow.ly",
    "cutt.ly", "shorte.st", "rebrand.ly", "buff.ly", "rb.gy",
}

IP_HOST_PATTERN = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def _extract_host(url):
    host = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    host = re.sub(r"^www\.", "", host, flags=re.IGNORECASE)
    host = host.split("/")[0].split(":")[0]
    return host.lower()


def analyze_urls(text):
    """Détecte les liens suspects dans un message : raccourcisseurs et IPs brutes."""
    reasons = []
    score = 0

    for url in URL_PATTERN.findall(text):
        host = _extract_host(url)
        if host in KNOWN_SHORTENERS:
            score += 25
            reasons.append(f"Contient un lien raccourci suspect : '{host}'")
        elif IP_HOST_PATTERN.match(host):
            score += 25
            reasons.append(f"Contient un lien pointant vers une adresse IP brute : '{host}'")
        else:
            score += 5
            reasons.append(f"Contient un lien : '{host}'")

    return score, reasons
