from oauth2client.client import OAuth2WebServerFlow
from os import environ

if False:

    CLIENT_ID = environ['GDOCS_CLIENT_ID']
    CLIENT_SECRET = environ['GDOCS_CLIENT_SECRET']
    SCOPES = ['https://spreadsheets.google.com/feeds/']

    flow = OAuth2WebServerFlow(CLIENT_ID, CLIENT_SECRET, " ".join(SCOPES))
    flow_info = flow.step1_get_device_and_user_codes()
    print "Enter the following code at %s: %s" % (flow_info.verification_url, flow_info.user_code)

    raw_input()

    credentials = flow.step2_exchange(device_flow_info=flow_info)
    print "Access token:", credentials.access_token
    print "Refresh token:", credentials.refresh_token

else:
    
    class FakeCred:
        access_token = 'ya29.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        #refresh_token = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    
    credentials = FakeCred()

import gspread
gc = gspread.authorize(credentials)

doc = gc.open_by_url('https://docs.google.com/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')

print doc.worksheets()
