from types import SimpleNamespace
from fastapi import HTTPException
from app.research import check_provider


def test_missing_key_makes_no_provider_requests(monkeypatch, capsys):
    def unexpected(*args):
        raise AssertionError('No network request should be made')
    monkeypatch.setattr(check_provider, 'hosted_selection', unexpected)
    assert not check_provider.check(SimpleNamespace(corplex_llm_api_key=''))
    assert 'No request sent' in capsys.readouterr().out


def test_check_uses_only_synthetic_evidence_and_requires_abstention(monkeypatch):
    calls = []
    def select(question, evidence, settings):
        calls.append((question, evidence))
        assert evidence[0]['chunk_id'] == 'synthetic-payment-check'
        return [{'text': evidence[0]['text']}] if len(calls) == 1 else []
    monkeypatch.setattr(check_provider, 'hosted_selection', select)
    assert check_provider.check(SimpleNamespace(corplex_llm_api_key='test-only'))
    assert len(calls) == 2
    monkeypatch.setattr(check_provider, 'hosted_selection', lambda *args: [{'text': 'Buyer shall pay USD 100.00 per month.'}])
    assert not check_provider.check(SimpleNamespace(corplex_llm_api_key='test-only'))


def test_provider_error_details_never_reach_terminal(monkeypatch, capsys):
    secret = 'test-secret-must-not-be-printed'
    def fail(*args):
        raise HTTPException(502, secret)
    monkeypatch.setattr(check_provider, 'hosted_selection', fail)
    assert not check_provider.check(SimpleNamespace(corplex_llm_api_key=secret))
    assert secret not in capsys.readouterr().out
