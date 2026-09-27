"""Create bucket-scoped tokens; write once to private files, never print credentials."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Refusing to redirect a credential-bearing request')


def api(base, token, path, data=None):
    url = urlsplit(base)
    if url.username or url.password or (url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost'))):
        raise ValueError('Use verified HTTPS or a localhost kubectl port-forward')
    request = Request(base.rstrip('/') + path,
                      data=None if data is None else json.dumps(data).encode(),
                      headers={'Authorization': 'Token ' + token, 'Content-Type': 'application/json'})
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        return json.load(response)


def scoped_tokens(base, token, org, bucket, save=None):
    organizations = api(base, token, '/api/v2/orgs?' + urlencode({'org': org}))['orgs']
    if len(organizations) != 1:
        raise ValueError('Expected exactly one organization')
    org_id = organizations[0]['id']
    buckets = api(base, token, '/api/v2/buckets?' + urlencode({'orgID': org_id, 'name': bucket}))['buckets']
    if len(buckets) != 1:
        raise ValueError('Expected exactly one bucket')
    result = {}
    for role, action in [('nodered', 'write'), ('grafana', 'read')]:
        result[role] = api(base, token, '/api/v2/authorizations', {
            'orgID': org_id, 'description': 'OT Security ' + role,
            'permissions': [{'action': action, 'resource': {'type': 'buckets', 'id': buckets[0]['id'], 'orgID': org_id}}]
        })['token']
        if save:
            save(role, result[role])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    base = os.environ['INFLUXDB_URL']
    url = urlsplit(base)
    if url.username or url.password or (url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost'))):
        raise ValueError('Use verified HTTPS or a localhost kubectl port-forward')
    output = args.output.resolve()
    root = Path(__file__).resolve().parents[1]
    if output == root or root in output.parents:
        raise ValueError('Secret directory must be outside the repository')
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    destinations = {'nodered': output/'influx-write.env', 'grafana': output/'grafana-influxdb.env'}
    if any(p.exists() for p in destinations.values()):
        raise FileExistsError('Refusing to overwrite existing token files')
    def save(role, token):
        path = destinations[role]
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            key = 'INFLUXDB_WRITE_TOKEN' if role == 'nodered' else 'INFLUXDB_READ_TOKEN'
            stream.write(key + '=' + token + '\n')
            stream.flush()
            os.fsync(stream.fileno())
    # Persist each token immediately: a later API error must not lose the first.
    scoped_tokens(base, os.environ['INFLUXDB_ADMIN_TOKEN'], os.environ['INFLUXDB_ORG'], os.environ['INFLUXDB_BUCKET'], save=save)
    print('Scoped tokens created. Store the two files securely; tokens are not printed.')


if __name__ == '__main__':
    main()
