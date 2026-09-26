import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

root = Path(__file__).resolve().parents[1]
command = ['node', str(root/'backend/node_modules/wrangler/bin/wrangler.js'), 'auth', 'token', '--json']
credentials = json.loads(subprocess.run(command, cwd=root/'backend', check=True, capture_output=True, text=True).stdout)
token = credentials['token']
account = '6555080ff3b2c930f707f7cb4746fa2d'
report = {}
for suffix in ('subscriptions', 'workers/account-settings', 'workers/subdomain'):
    request = urllib.request.Request(f'https://api.cloudflare.com/client/v4/accounts/{account}/{suffix}', headers={'Authorization': 'Bearer '+token})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
        report[suffix] = value
    except urllib.error.HTTPError as exc:
        report[suffix] = {'http_status':exc.code}
(root/'state/cloudflare-plan.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
