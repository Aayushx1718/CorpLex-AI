"""Opt-in live provider smoke check using only original synthetic text (no database)."""
from fastapi import HTTPException
from app.config import get_settings
from app.research.service import hosted_selection


def check(settings) -> bool:
    if not settings.corplex_llm_api_key:
        print('NOT CONFIGURED: set CORPLEX_LLM_API_KEY securely on the backend. No request sent.')
        return False
    source = 'Synthetic demo agreement. Buyer shall pay USD 100.00 per month.'
    evidence = [{'chunk_id': 'synthetic-payment-check', 'text': source,
                 'char_start': 0, 'char_end': len(source)}]
    try:
        selected = hosted_selection('What monthly payment is explicitly required?', evidence, settings)
        if not selected or not any('USD 100.00' in row['text'] and 'month' in row['text'] for row in selected):
            print('FAILED: supported payment question did not return the expected exact evidence.')
            return False
        unsupported = hosted_selection('What governing law is explicitly stated?', evidence, settings)
        if unsupported:
            print('FAILED: unsupported governing-law question did not abstain.')
            return False
    except HTTPException:
        # Never print exception/provider bodies: they may contain request credentials or text.
        print('FAILED: provider request or source validation failed. Check the key, API billing, model access and network connectivity locally. No provider error body is displayed.')
        return False
    print('PASSED: hosted payment quote and unsupported-question abstention. Two synthetic requests; no uploaded contracts sent. This is a smoke check, not a quality benchmark.')
    return True


def main() -> int:
    return 0 if check(get_settings()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
