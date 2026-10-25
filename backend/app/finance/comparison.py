import difflib
import re
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class CompareRequest(BaseModel):
    left_document_id: UUID
    right_document_id: UUID

    @model_validator(mode='after')
    def distinct(self):
        if self.left_document_id==self.right_document_id:raise ValueError('Choose two distinct document versions.')
        return self


def compare(connection,body):
    documents={row['id']:dict(row) for row in connection.execute(text('''SELECT v.id,v.contract_id,v.version_number,c.title,s.canonical_text
        FROM document_versions v JOIN contracts c ON c.id=v.contract_id JOIN document_sources s ON s.document_version_id=v.id
        WHERE v.id=ANY(:ids)'''),{'ids':[body.left_document_id,body.right_document_id]}).mappings()}
    if len(documents)!=2:raise HTTPException(404,'Both source document versions must exist.')
    if any(len(row['canonical_text'])>100000 for row in documents.values()):
        raise HTTPException(413,'Comparison is limited to 100,000 extracted characters per version.')
    sources=[]
    for doc_id in [body.left_document_id,body.right_document_id]:
        clauses=[dict(row) for row in connection.execute(text('SELECT id,ordinal,heading,text_content,char_start,char_end FROM clauses WHERE document_version_id=:id ORDER BY ordinal LIMIT 201'),{'id':doc_id}).mappings()]
        if len(clauses)>200:raise HTTPException(413,'Comparison is limited to 200 clauses per version.')
        sources.append(clauses)
    left,right=sources
    similarities=[]
    if left and right:
        vectorizer=TfidfVectorizer(ngram_range=(1,2),strip_accents='unicode')
        try:
            matrix=vectorizer.fit_transform([row['text_content'] for row in left+right])
            similarity=cosine_similarity(matrix[:len(left)],matrix[len(left):])
            similarities=sorted([(float(similarity[i,j]),i,j) for i in range(len(left)) for j in range(len(right))],key=lambda item:(-item[0],item[1],item[2]))
        except ValueError:pass
    used_left,used_right=set(),set()
    pairs=[]
    for score,i,j in similarities:
        if score<.20:break
        if i in used_left or j in used_right:continue
        used_left.add(i);used_right.add(j)
        same=' '.join(left[i]['text_content'].split())==' '.join(right[j]['text_content'].split())
        pairs.append({'left':left[i],'right':right[j],'lexical_similarity':score,
                      'status':'unchanged' if same else 'modified','near_duplicate':score>=.90})
    a,b=documents[body.left_document_id],documents[body.right_document_id]
    diff=list(difflib.unified_diff(a['canonical_text'].splitlines(),b['canonical_text'].splitlines(),fromfile=f"{a['title']} v{a['version_number']}",tofile=f"{b['title']} v{b['version_number']}",lineterm=''))
    terms={}
    for doc_id in [body.left_document_id,body.right_document_id]:
        terms[str(doc_id)]=[dict(row) for row in connection.execute(text('''SELECT o.kind,o.amount::text AS amount,o.currency,o.due_date,o.recurrence,o.review_status,o.clause_id
            FROM obligations o JOIN clauses c ON c.id=o.clause_id WHERE c.document_version_id=:id ORDER BY c.ordinal,o.id'''),{'id':doc_id}).mappings()]
    return {'left':{k:v for k,v in a.items() if k!='canonical_text'},'right':{k:v for k,v in b.items() if k!='canonical_text'},
            'same_contract':a['contract_id']==b['contract_id'],'pairs':pairs,
            'left_only':[row for i,row in enumerate(left) if i not in used_left],
            'right_only':[row for i,row in enumerate(right) if i not in used_right],
            'diff':'\n'.join(diff[:2000]),'diff_truncated':len(diff)>2000,'obligation_terms':terms,
            'notice':'Lexical alignment and textual differences only. Candidate terms may differ without creating a legal conflict; human review is required.'}


def build_comparison_router(engine):
    router=APIRouter(prefix='/api/comparison',tags=['cross-contract comparison'])
    @router.post('')
    def run(body:CompareRequest):
        try:
            with engine.connect() as connection:return compare(connection,body)
        except SQLAlchemyError:raise HTTPException(503,'Comparison storage unavailable.') from None
    return router
