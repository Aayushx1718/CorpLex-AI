import re
from uuid import UUID, uuid5
import numpy as np
import faiss
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

INDEX_VERSION = 'chunks900-overlap150-v1'
EMBEDDING_MODEL = 'corpus-local-lsa-v1'


def chunks(clause: dict) -> list[dict]:
    value, offset = clause['text_content'], clause['char_start']
    output, start = [], 0
    while start < len(value):
        end = min(start + 900, len(value))
        if end < len(value):
            boundary = value.rfind(' ', start + 450, end)
            if boundary > start:
                end = boundary
        text = value[start:end]
        if text.strip():
            key = f"{clause['id']}|{INDEX_VERSION}|{start}|{end}"
            output.append({**clause, 'chunk_id': uuid5(UUID('298719b1-02c5-4f1d-9883-348b8aee0be0'), key),
                           'chunk_number': len(output), 'text': text,
                           'char_start': offset + start, 'char_end': offset + end})
        if end == len(value):
            break
        next_start = max(start + 1, end - 150)
        while next_start < end and not value[next_start - 1].isspace():
            next_start += 1
        start = next_start
    return output


class CorpusLSA(Embeddings):
    """Local latent vectors, NOT pretrained semantic embeddings."""
    def __init__(self, documents):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=8000, sublinear_tf=True,
                                        stop_words='english', token_pattern=r'(?u)\b\w+\b')
        matrix = self.vectorizer.fit_transform(documents)
        dimensions = min(128, matrix.shape[0] - 1, matrix.shape[1] - 1)
        self.reducer = TruncatedSVD(n_components=dimensions, random_state=42) if dimensions >= 2 else None
        self.lexical = normalize(matrix)
        dense = self.reducer.fit_transform(matrix) if self.reducer else matrix.toarray()
        self.dense = normalize(dense).astype('float32')

    def embed_documents(self, texts):
        matrix = self.vectorizer.transform(texts)
        dense = self.reducer.transform(matrix) if self.reducer else matrix.toarray()
        return normalize(dense).astype('float32').tolist()

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def expanded(question: str) -> str:
    synonyms = {'pay': 'payment fees compensation', 'payment': 'pay fees compensation',
                'terminate': 'termination notice end', 'renew': 'renewal expiration',
                'late': 'delay penalty credit', 'confidential': 'confidentiality information',
                'penalties': 'penalty delay credit', 'expires': 'expiration renewal',
                'parties': 'parties buyer vendor employer client provider'}
    words = re.findall(r'\w+', question.lower())
    return question + ' ' + ' '.join(synonyms.get(word, '') for word in words)


def hostile(value: str) -> bool:
    return bool(re.search(r'ignore\b.{0,50}\binstructions|system prompt|reveal\b.{0,30}\bsecret|api[ _-]?key|pretend you|disregard\b.{0,40}\binstructions', value, re.I | re.S))


def retrieve(rows: list[dict], question: str, mode='hybrid', k=4) -> list[dict]:
    if not rows or hostile(question) or re.search(r'\b(legal advice|should I sue|is this legal|enforceable|win in court)\b', question, re.I):
        return []
    documents = [Document(page_content=row['text'], metadata={'chunk_id': str(row['chunk_id'])}) for row in rows]
    try:
        encoder = CorpusLSA([document.page_content for document in documents])
    except ValueError:
        return []
    query = expanded(question)
    lexical_query = encoder.vectorizer.transform([query])
    if not lexical_query.nnz:
        return []
    lexical = np.asarray((encoder.lexical @ normalize(lexical_query).T).toarray()).reshape(-1)
    index = faiss.IndexFlatIP(encoder.dense.shape[1])
    index.add(encoder.dense)
    distances, indices = index.search(np.asarray([encoder.embed_query(query)], dtype='float32'), len(rows))
    dense = np.zeros(len(rows))
    dense[indices[0]] = distances[0]
    lex_order = np.argsort(-lexical, kind='stable')
    dense_order = np.argsort(-dense, kind='stable')
    lex_rank = {int(i): rank for rank, i in enumerate(lex_order, 1)}
    dense_rank = {int(i): rank for rank, i in enumerate(dense_order, 1)}
    scores = lexical if mode == 'lexical' else dense if mode == 'dense' else np.array([
        1 / (60 + lex_rank[i]) + 1 / (60 + dense_rank[i]) for i in range(len(rows))])
    result = []
    for i in sorted(range(len(rows)), key=lambda i: (-float(scores[i]), str(rows[i]['chunk_id']))):
        row = rows[i]
        if lexical[i] < .10 or hostile(row['text']):
            continue
        if re.search(r'governing law|jurisdiction', question, re.I) and not re.search(r'governed by|governing law|jurisdiction', row['text'], re.I):
            continue
        currencies = re.findall(r'\b(?:USD|EUR|GBP|INR|CAD|AUD|JPY|CHF)\b', question)
        if currencies and not all(code in row['text'] for code in currencies):
            continue
        result.append({**row, 'retrieval_score': float(scores[i]), 'lexical_similarity': float(lexical[i])})
        if len(result) >= k:
            break
    return result
