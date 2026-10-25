"""Ephemeral protected-mode container smoke test. Never prints generated tokens."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import httpx

root=Path(__file__).resolve().parents[1]
project='corplex-protected-check-'+secrets.token_hex(4)
password,access,review=(secrets.token_urlsafe(40) for _ in range(3))
env={**os.environ,'DOCKER_CONFIG':os.getenv('DOCKER_CONFIG','/tmp/corplex-docker'),'APP_ENV':'production',
     'POSTGRES_PASSWORD':password,'CONTAINER_DATABASE_URL':f'postgresql+psycopg://corplex:{password}@db:5432/corplex',
     'CORPLEX_ACCESS_TOKEN':access,'CORPLEX_REVIEW_TOKEN':review,'APP_PORT':'8081',
     'CORS_ORIGINS':json.dumps(['http://localhost:8081','http://127.0.0.1:8081'])}
command=['docker','compose','-p',project,'-f','compose.app.yaml']
try:
    subprocess.run(command+['up','--no-build','-d','--wait','--wait-timeout','180'],cwd=root,env=env,check=True)
    with httpx.Client(base_url='http://127.0.0.1:8081',timeout=30) as client:
        assert client.get('/api/health').status_code==200
        assert client.get('/api/contracts').status_code==401
        headers={'Authorization':f'Bearer {access}'}
        assert client.get('/api/contracts',headers=headers).status_code==200
        source=root/'samples/generated/vendor.docx'
        with source.open('rb') as file:
            response=client.post('/api/contracts',headers=headers,data={'contract_type':'vendor'},
                files={'file':('vendor.docx',file,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        assert response.status_code==201,response.status_code
        document=response.json()['document']
        run=client.post('/api/workflows',headers=headers,json={'document_id':document['id']})
        assert run.status_code==201,run.status_code
        run_id=run.json()['id']
        decision={'decision':'approved','reviewer':'Synthetic protected reviewer','note':'Checked this original synthetic source report for the smoke test.'}
        assert client.post(f'/api/workflows/{run_id}/review',headers=headers,json=decision).status_code==403
        authorized={**headers,'X-Review-Token':review}
        assert client.post(f'/api/workflows/{run_id}/review',headers=authorized,json=decision).status_code==200
        assert client.get(f'/api/workflows/{run_id}/export',headers=headers).status_code==200
        assert client.post('/api/contracts',headers={**headers,'Origin':'https://untrusted.example'}).status_code==403
    browser_check=Path('/tmp/corplex-browser/protected.cjs')
    if browser_check.is_file():
        subprocess.run(['node',str(browser_check)],env={**env,'CHECK_ACCESS_TOKEN':access},check=True)
    print('Protected Docker checks passed: access 401, authorized read/upload, reviewer 403/200, approval export and origin rejection.')
finally:
    # Only this newly created, random-name synthetic test project is stopped.
    subprocess.run(command+['stop'],cwd=root,env=env,check=False)
