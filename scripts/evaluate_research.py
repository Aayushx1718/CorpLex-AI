"""Frozen synthetic retrieval comparison; no provider calls or invented QA scores."""
import json
from pathlib import Path
import sys
from uuid import NAMESPACE_URL,uuid5
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.research.retrieval import chunks,retrieve

root=Path(__file__).resolve().parents[1]
fixture=json.loads((root/'samples/contracts/research-evaluation.json').read_text())
rows=[]
for name,clauses in fixture['documents'].items():
    position=0
    for number,value in enumerate(clauses,1):
        clause={'id':uuid5(NAMESPACE_URL,f'{name}-{number}'),'document_version_id':name,'text_content':value,'char_start':position}
        rows.extend(chunks(clause));position+=len(value)+1
reports={}
for mode in ['lexical','dense','hybrid']:
    answers,reciprocal,abstentions,valid_citations,quotes=0,0.,0,0,0
    cases=[]
    for case in fixture['questions']:
        scoped=[row for row in rows if row['document_version_id'] in case['scope']]
        found=retrieve(scoped,case['question'],mode,k=3)
        relevant=[i for i,row in enumerate(found,1) if case['gold'] and case['gold'] in row['text']]
        if case['gold']:
            answers+=bool(relevant);reciprocal+=1/relevant[0] if relevant else 0
        else:abstentions+=not bool(found)
        for row in found:
            original=next(source for source in scoped if source['chunk_id']==row['chunk_id'])
            quotes+=1;valid_citations+=row['text']==original['text']
        cases.append({'question':case['question'],'gold':case['gold'],'top3_contains_gold':bool(relevant),'abstained':not bool(found)})
    positive=sum(case['gold'] is not None for case in fixture['questions']);negative=len(fixture['questions'])-positive
    reports[mode]={'answerable_count':positive,'unanswerable_or_hostile_count':negative,'recall_at_3':answers/positive,
                   'mean_reciprocal_rank_at_3':reciprocal/positive,'abstention_accuracy':abstentions/negative,
                   'exact_citation_quote_rate':valid_citations/quotes if quotes else None,'cases':cases}
result={'dataset':fixture['dataset'],'license':fixture['license'],'created_at':datetime.now(timezone.utc).isoformat(),
        'methods':reports,'embedding_model':'corpus-local-lsa-v1','hosted_generation_executed':False,
        'limitations':['Twelve small synthetic questions, not a real-world accuracy claim.','No pretrained semantic embeddings or free-form answer generation evaluated.','Hosted provider validation requires a securely supplied API key.']}
output=root/'docs/research-evaluation.json';output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({key:{k:v for k,v in value.items() if k!='cases'} for key,value in reports.items()},indent=2))
