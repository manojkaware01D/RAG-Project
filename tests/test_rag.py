from rag import SEED_DOCUMENTS, parse_github_repository_url, retrieve_passages, split_passages


def test_wire_query_retrieves_fee_schedule_passages():
    results = retrieve_passages("When is a wire transfer fee charged?", SEED_DOCUMENTS)

    assert results
    assert "domestic wire" in results[0]["text"].lower()
    assert results[0]["document"]["id"] == "fee-schedule"
    assert {result["document"]["id"] for result in results} == {"fee-schedule"}


def test_unmatched_query_returns_no_passages():
    assert retrieve_passages("volcanic observatory telescope", SEED_DOCUMENTS) == []


def test_split_passages_limits_long_chunks():
    passages = split_passages("word " * 500, max_chars=100)

    assert len(passages) > 1
    assert all(len(passage) <= 100 for passage in passages)


def test_parse_public_github_repository_url():
    assert parse_github_repository_url("https://github.com/octocat/Hello-World.git") == (
        "octocat",
        "Hello-World",
    )