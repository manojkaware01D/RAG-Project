import base64
import math
import re
import unicodedata
from collections import Counter
from urllib.parse import urlparse

import requests


SEED_DOCUMENTS = [
    {
        "id": "checking-guide",
        "title": "Everyday checking account guide",
        "category": "Accounts",
        "updated": "Updated Oct 08, 2026",
        "content": (
            "Everyday Checking has a $5 monthly maintenance fee. The fee is waived when the account "
            "maintains a $500 minimum daily balance or receives at least $500 in qualifying electronic "
            "deposits during the statement cycle. Qualifying deposits include payroll, government benefits, "
            "and payments from an eligible third-party provider. Internal transfers and mobile check deposits "
            "do not count toward the deposit waiver. The account includes a debit card and online bill pay "
            "at no additional monthly charge."
        ),
    },
    {
        "id": "debit-card-help",
        "title": "Debit card service and disputes",
        "category": "Cards",
        "updated": "Updated Oct 02, 2026",
        "content": (
            "If a debit card is lost or stolen, lock it immediately in the Northstar mobile app or online "
            "banking, then call the card support line at 1-800-555-0148 to request a replacement. Locking a "
            "card temporarily blocks new purchases and can be reversed in the app if the card is found. "
            "Report an unrecognized debit card transaction promptly; cardholders should contact us within "
            "60 days of the statement date. We will explain the investigation timeline when the claim is opened."
        ),
    },
    {
        "id": "fee-schedule",
        "title": "Personal banking fee schedule",
        "category": "Fees",
        "updated": "Updated Sep 26, 2026",
        "content": (
            "Outgoing domestic wire transfers have a $25 fee. Outgoing international wire transfers have a "
            "$45 fee. Incoming domestic wires are free. Using an out-of-network ATM has a $3 Northstar fee; "
            "the ATM owner may also charge a separate fee. A cashier's check costs $8. Fees can vary by "
            "account package, so verify the customer's current account terms before quoting a charge."
        ),
    },
    {
        "id": "savings-overview",
        "title": "Northstar savings account overview",
        "category": "Accounts",
        "updated": "Updated Sep 18, 2026",
        "content": (
            "Northstar Growth Savings has no monthly maintenance fee and no minimum opening deposit. The "
            "interest rate is variable and the annual percentage yield may change at any time. Current rates "
            "are published on the bank's rates page and should be checked before quoting an APY."
        ),
    },
    {
        "id": "fraud-response",
        "title": "Fraud and account security response",
        "category": "Security",
        "updated": "Updated Sep 11, 2026",
        "content": (
            "For suspected account fraud, contact Northstar immediately at 1-800-555-0148. A specialist is "
            "available 24 hours a day, 7 days a week. Customers should never share a one-time passcode, full "
            "password, or PIN with anyone who contacts them. Bank staff will not ask a customer to move money "
            "to a so-called safe account."
        ),
    },
    {
        "id": "personal-loans",
        "title": "Personal lending and prequalification",
        "category": "Lending",
        "updated": "Updated Aug 30, 2026",
        "content": (
            "Customers may check personal loan prequalification online. Checking prequalification uses a soft "
            "credit inquiry and does not affect the customer's credit score. A full application may require a "
            "hard credit inquiry, which can affect a credit score. Prequalification is not a loan approval or "
            "a guarantee of an offered rate."
        ),
    },
]

MAX_REPO_FILES = 8
MAX_FILE_BYTES = 75_000
MIN_RELEVANCE_SCORE = 0.05
DOCUMENT_EXTENSIONS = {".md", ".mdx", ".rst", ".txt", ".csv"}
STOP_WORDS = set(
    "a an and are as at be been being by can could did do does doing for from had has have how i in "
    "is it its may might of on or should that the their them then there these they this those to was "
    "were what when where which who why will with would you your".split()
)


def split_passages(text: str, max_chars: int = 900) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]
    passages: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                passages.append(current)
                current = ""
            passages.extend(sentence[index : index + max_chars] for index in range(0, len(sentence), max_chars))
        elif current and len(current) + len(sentence) + 1 > max_chars:
            passages.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        passages.append(current)
    return passages


def retrieve_passages(query: str, documents: list[dict], limit: int = 4) -> list[dict]:
    query = query.strip()
    if not query or not documents:
        return []

    passages = [
        {"text": passage, "document": document}
        for document in documents
        for passage in split_passages(document.get("content", ""))
    ]
    if not passages:
        return []

    def terms(text: str) -> list[str]:
        normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
        words = [word for word in re.findall(r"[a-z0-9]+", normalized) if len(word) > 1 and word not in STOP_WORDS]
        return words + [f"{first} {second}" for first, second in zip(words, words[1:])]

    vectors = [Counter(terms(query)), *(Counter(terms(item["text"])) for item in passages)]
    if not vectors[0]:
        return []

    document_frequency = Counter(term for vector in vectors for term in vector)
    document_count = len(vectors)
    inverse_frequency = {
        term: math.log((document_count + 1) / (frequency + 1)) + 1
        for term, frequency in document_frequency.items()
    }

    def weighted(vector: Counter) -> dict[str, float]:
        return {term: frequency * inverse_frequency[term] for term, frequency in vector.items()}

    query_vector = weighted(vectors[0])
    query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
    scores = []
    for vector, passage in zip(vectors[1:], passages):
        passage_vector = weighted(vector)
        passage_norm = math.sqrt(sum(value * value for value in passage_vector.values()))
        dot_product = sum(value * passage_vector.get(term, 0.0) for term, value in query_vector.items())
        score = dot_product / (query_norm * passage_norm) if query_norm and passage_norm else 0.0
        scores.append((score, passage))

    ranked = sorted(scores, key=lambda item: item[0], reverse=True)
    return [
        {**passage, "score": float(score)}
        for score, passage in ranked[:limit]
        if score >= MIN_RELEVANCE_SCORE
    ]


def parse_github_repository_url(value: str) -> tuple[str, str]:
    parsed = urlparse(value.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.hostname != "github.com" or len(parts) != 2:
        raise ValueError("Enter a public GitHub URL in the form https://github.com/owner/repository.")
    owner, repository = parts
    repository = repository.removesuffix(".git")
    if not re.fullmatch(r"[\w.-]+", owner) or not re.fullmatch(r"[\w.-]+", repository):
        raise ValueError("That GitHub repository URL is not valid.")
    return owner, repository


def import_public_repository(repository_url: str) -> list[dict[str, str]]:
    owner, repository_name = parse_github_repository_url(repository_url)
    api_url = f"https://api.github.com/repos/{owner}/{repository_name}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Ledgerline-Banking-RAG"}

    def get_json(url: str) -> dict:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code in (403, 429):
            raise RuntimeError("GitHub API rate limit reached. Try again later.")
        if response.status_code == 404:
            raise ValueError("Repository not found. Only public repositories can be imported.")
        if not response.ok:
            raise RuntimeError(f"GitHub returned an error ({response.status_code}).")
        return response.json()

    repository = get_json(api_url)
    branch = repository["default_branch"]
    full_name = repository["full_name"]
    tree = get_json(f"{api_url}/git/trees/{branch}?recursive=1")
    entries = [
        entry
        for entry in tree.get("tree", [])
        if entry.get("type") == "blob"
        and entry.get("size", MAX_FILE_BYTES + 1) <= MAX_FILE_BYTES
        and (
            entry["path"].lower().endswith(tuple(DOCUMENT_EXTENSIONS))
            or entry["path"].split("/")[-1].lower().startswith("readme")
        )
    ]

    def priority(entry: dict) -> tuple[int, str]:
        path = entry["path"]
        filename = path.split("/")[-1].lower()
        if filename.startswith("readme"):
            return 0, path
        if re.search(r"(^|/)docs?/", path, flags=re.IGNORECASE):
            return 1, path
        return 2, path

    entries = sorted(entries, key=priority)[:MAX_REPO_FILES]
    if not entries:
        raise ValueError("No small README, Markdown, text, or CSV files were found.")

    imported: list[dict[str, str]] = []
    for entry in entries:
        path = entry["path"]
        content_url = f"{api_url}/contents/{path}?ref={requests.utils.quote(branch, safe='')}"
        file_data = get_json(content_url)
        if file_data.get("encoding") != "base64" or not file_data.get("content"):
            continue
        content = base64.b64decode(file_data["content"]).decode("utf-8", errors="replace").strip()
        if content:
            imported.append(
                {
                    "title": f"{full_name} / {path}",
                    "content": content,
                    "source_repo": full_name,
                    "source_path": path,
                }
            )

    if not imported:
        raise RuntimeError("GitHub files could not be read. Check the repository and try again.")
    return imported