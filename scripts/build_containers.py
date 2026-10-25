"""Build images with optional standard corporate proxy/CA support, preserving TLS."""
import os
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlsplit,urlunsplit

root=Path(__file__).resolve().parents[1]
arguments=[]
for name in ['HTTP_PROXY','HTTPS_PROXY']:
    raw=os.getenv(name)
    if raw:
        parsed=urlsplit(raw)
        if parsed.username or parsed.password:
            raise SystemExit('Authenticated proxy URLs need a separately reviewed secure build configuration.')
        # Build containers may not resolve a host-only proxy service name.
        address=socket.gethostbyname(parsed.hostname)
        authority=f'{address}:{parsed.port or 80}'
        arguments+=['--build-arg',name+'='+urlunsplit((parsed.scheme,authority,parsed.path,parsed.query,parsed.fragment))]
ca=os.getenv('SSL_CERT_FILE') or os.getenv('REQUESTS_CA_BUNDLE')
if ca and Path(ca).is_file():arguments+=['--secret',f'id=build_ca,src={ca}']
env=dict(os.environ)
env.setdefault('DOCKER_CONFIG','/tmp/corplex-docker')
for name in ['backend','frontend']:
    extra=['--build-arg','INCLUDE_ML=true'] if name=='backend' and os.getenv('INCLUDE_ML')=='true' else []
    subprocess.run(['docker','buildx','build','--load','--tag',f'corplex-app-{name}','--file',f'{name}/Dockerfile',*arguments,*extra,'.'],cwd=root,env=env,check=True)
