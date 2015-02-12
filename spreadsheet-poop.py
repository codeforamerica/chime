from oauth2client.client import OAuth2WebServerFlow
from os import environ

class FakeCred:
    access_token = 'ya29.GAHsoO1OuoMVG10lYxDdUIHQld4kqdwfbed5zPyGfZVzvtVq6zN8SlKb2dE1-AMBELn92-n7wG_r5A'
    #refresh_token = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

if True:

    CLIENT_ID = environ['GDOCS_CLIENT_ID']
    CLIENT_SECRET = environ['GDOCS_CLIENT_SECRET']
    SCOPES = ['https://spreadsheets.google.com/feeds/',

              # http://stackoverflow.com/questions/24293523/im-trying-to-access-google-drive-through-the-cli-but-keep-getting-not-authori
              'https://docs.google.com/feeds',
              
              #'https://www.googleapis.com/auth/drive',
              #'https://www.googleapis.com/auth/drive.file',
              #'https://www.googleapis.com/auth/plus.login',
              ]

    try:
        flow = OAuth2WebServerFlow(CLIENT_ID, CLIENT_SECRET, SCOPES)
        flow_info = flow.step1_get_device_and_user_codes()
        print "Enter the following code at %s: %s" % (flow_info.verification_url, flow_info.user_code)
    except Exception as e:
        print e.args, e.message
        raise

    raw_input()

    credentials = flow.step2_exchange(device_flow_info=flow_info)
    print "Access token:", credentials.access_token
    print "Refresh token:", credentials.refresh_token

else:
    
    credentials = FakeCred()

import gspread, json
from urllib import urlencode

try:
    gc = gspread.authorize(credentials)
    url = 'https://www.googleapis.com/drive/v2/files/12jUfaRBd-CU1_6BGeLFG1_qoi7Fw_vRC_SXv36eDzM0/copy'
    print 'POST to', url
    resp = gc.session.post(url, '{}', headers={'Content-Type': 'application/json'})
except Exception as e:
    print e
    print e.response.getheaders()
    print e.response.read()
    raise

info = json.load(resp)
print '{id} - {title}'.format(**info)

try:
    gc = gspread.authorize(credentials)
    url = 'https://www.googleapis.com/drive/v2/files/{id}'.format(**info)
    print 'PATCH to', url
    gc.session.request('PATCH', url, '{"title": "Good TIMES"}', headers={'Content-Type': 'application/json'})
except Exception as e:
    print e
    print e.response.getheaders()
    print e.response.read()
    raise

try:
    perm = dict(
        role='writer',
        type='user',
        emailAddress='frances@codeforamerica.org',
        value='frances@codeforamerica.org'
        )
    query = urlencode(dict(sendNotificationEmails='true', emailMessage='Yo.'))
    gc = gspread.authorize(credentials)
    url = 'https://www.googleapis.com/drive/v2/files/{id}/permissions?{}'.format(query, **info)
    print 'POST to', url
    gc.session.post(url, json.dumps(perm), headers={'Content-Type': 'application/json'})
except Exception as e:
    print e
    print e.response.getheaders()
    print e.response.read()
    raise

exit()

doc = gc.open_by_url('https://docs.google.com/a/codeforamerica.org/spreadsheets/d/12jUfaRBd-CU1_6BGeLFG1_qoi7Fw_vRC_SXv36eDzM0/edit#gid=0')

print doc.worksheets()
