import json
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from typing import Annotated
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

Money = Annotated[Decimal, Field(ge=0,max_digits=20,decimal_places=4,allow_inf_nan=False)]
Quantity = Annotated[Decimal, Field(ge=0,le=36500,max_digits=12,decimal_places=4,allow_inf_nan=False)]


class ScenarioLine(BaseModel):
    obligation_id: UUID
    quantity: Quantity = Decimal('1')
    assumed_rate: Money | None = None
    cap: Money | None = None
    assumption_note: str = Field(default='',max_length=500)


class ScenarioRequest(BaseModel):
    document_id: UUID
    name: str = Field(min_length=1,max_length=100)
    currency: str = Field(pattern='^[A-Z]{3}$')
    include_unreviewed: bool = False
    lines: list[ScenarioLine] = Field(min_length=1,max_length=20)

    @field_validator('name')
    @classmethod
    def name_clean(cls,value):
        if not value.strip() or '\x00' in value:raise ValueError('A valid name is required.')
        return value.strip()

    @model_validator(mode='after')
    def unique_lines(self):
        if len({line.obligation_id for line in self.lines})!=len(self.lines):
            raise ValueError('Do not count an obligation twice in the same scenario.')
        return self


def simulate(connection, body):
    rows=connection.execute(text('''SELECT o.*,c.document_version_id,c.text_content,c.char_start,c.char_end
        FROM obligations o JOIN clauses c ON c.id=o.clause_id WHERE o.id=ANY(:ids)'''),
        {'ids':[line.obligation_id for line in body.lines]}).mappings().all()
    indexed={row['id']:row for row in rows}
    results=[]
    with localcontext() as context:
        context.prec=50
        total=Decimal('0')
        for line in body.lines:
            source=indexed.get(line.obligation_id)
            if not source or source['document_version_id']!=body.document_id:
                raise HTTPException(409,'Every obligation must belong to the selected document version.')
            if source['review_status']=='rejected':raise HTTPException(409,'Rejected obligations cannot enter a scenario.')
            if source['review_status']!='approved' and not body.include_unreviewed:
                raise HTTPException(409,'Review obligations first or explicitly include unreviewed candidates.')
            if source['currency'] and source['currency']!=body.currency:
                raise HTTPException(422,'Mixed currencies are unsupported. No implicit currency conversion is performed.')
            rate=line.assumed_rate if line.assumed_rate is not None else source['amount']
            if rate is None:raise HTTPException(422,'No single source amount exists. Supply an explicit assumed rate and assumption note.')
            if (line.assumed_rate is not None or line.cap is not None or line.quantity!=1 or source['review_status']!='approved') and len(line.assumption_note.strip())<10:
                raise HTTPException(422,'Explain quantity, cap, rate overrides or unreviewed-source assumptions in at least 10 characters.')
            uncapped=rate*line.quantity
            amount=min(uncapped,line.cap) if line.cap is not None else uncapped
            amount=amount.quantize(Decimal('.0001'),rounding=ROUND_HALF_EVEN)
            total+=amount
            results.append({'obligation_id':str(source['id']),'clause_id':str(source['clause_id']),
                            'source_text':source['text_content'],'source_char_start':source['char_start'],'source_char_end':source['char_end'],
                            'source_review_status':source['review_status'],'rate_origin':'user_assumption' if line.assumed_rate is not None else 'extracted_term',
                            'rate':str(rate),'quantity':str(line.quantity),'cap':str(line.cap) if line.cap is not None else None,
                            'uncapped_amount':str(uncapped),'amount':str(amount),'assumption_note':line.assumption_note})
        if total>=Decimal('10000000000000000'):raise HTTPException(422,'Scenario total exceeds the supported storage range.')
    return {'currency':body.currency,'formula_version':'sum-min-rate-times-quantity-cap-v1',
            'formula':'sum(min(rate × quantity, cap)) where a cap is explicitly supplied; otherwise rate × quantity',
            'rounding':'Each line rounded to 4 decimal places, half-even, before summation.',
            'lines':results,'amount':str(total),'hypothetical':True,
            'notice':'User-assumption scenario, not actual losses, an outstanding balance, contract value or a legal determination.'}


def build_finance_router(engine):
    router=APIRouter(prefix='/api/finance',tags=['financial scenarios'])

    @router.post('/scenarios',status_code=201)
    def create(body:ScenarioRequest):
        try:
            with engine.begin() as connection:
                result=simulate(connection,body)
                scenario_id=uuid4()
                connection.execute(text('''INSERT INTO exposure_scenarios(id,document_version_id,name,formula_version,assumptions,result_amount,currency)
                    VALUES (:id,:document,:name,:formula,CAST(:assumptions AS jsonb),:amount,:currency)'''),
                    {'id':scenario_id,'document':body.document_id,'name':body.name,'formula':result['formula_version'],
                     'assumptions':json.dumps(result),'amount':Decimal(result['amount']),'currency':body.currency})
                for line in body.lines:
                    connection.execute(text('INSERT INTO scenario_obligations(scenario_id,obligation_id) VALUES (:scenario,:obligation)'),{'scenario':scenario_id,'obligation':line.obligation_id})
                connection.execute(text("INSERT INTO audit_events(actor_id,action,entity_type,entity_id) VALUES ('local-development','scenario.created','exposure_scenario',:id)"),{'id':scenario_id})
                return {'id':scenario_id,'document_id':body.document_id,'name':body.name,**result}
        except SQLAlchemyError:
            raise HTTPException(503,'Scenario storage unavailable.') from None

    @router.get('/scenarios/{scenario_id}')
    def get(scenario_id:UUID):
        try:
            with engine.connect() as connection:
                row=connection.execute(text('SELECT id,document_version_id,name,assumptions,created_at FROM exposure_scenarios WHERE id=:id'),{'id':scenario_id}).mappings().first()
                if not row:raise HTTPException(404,'Scenario not found.')
                return {'id':row['id'],'document_id':row['document_version_id'],'name':row['name'],'created_at':row['created_at'],**row['assumptions']}
        except SQLAlchemyError:raise HTTPException(503,'Scenario storage unavailable.') from None
    return router
