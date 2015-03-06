''' Setup script for new Chime instance in EC2.

Asks for Github login credentials and desired repository
name to create under https://github.com/chimecms organization.

Requires four environment variables:
- GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET for Github authorization.
- AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for Amazon EC2 setup.

Follows the process described here:
  https://github.com/codeforamerica/ceviche-cms/issues/39#issuecomment-72957188

'''
from time import sleep
from bizarro.setup import functions

# Establish some baseline details.
github_client_id, github_client_secret, gdocs_client_id, gdocs_client_secret, \
    username, password, reponame, ec2, route53 = functions.get_input()

# Create a new authorization with Github.
github_auth_id, github_temporary_token = functions.get_github_authorization(
    github_client_id, github_client_secret, (username, password))

# Ask for Google Docs credentials and create an authentication spreadsheet.
gdocs_credentials = functions.authenticate_google(gdocs_client_id, gdocs_client_secret)
sheet_url = functions.create_google_spreadsheet(gdocs_credentials, reponame)

# Verify status of Github authorization.
functions.verify_github_authorization(
    github_client_id, github_client_secret, github_temporary_token, github_auth_id)

# Set up EC2 instance.
if functions.check_repo_state(reponame, github_temporary_token):
    raise RuntimeError('Repository {} already exists, not going to run EC2'.format(reponame))

instance = functions.create_ec2_instance(
    ec2, reponame, sheet_url, gdocs_client_id, gdocs_client_secret, github_temporary_token)

while True:
    print '    Waiting for', reponame
    sleep(30)

    if functions.check_repo_state(reponame, github_temporary_token):
        print '-->', 'https://github.com/chimecms/{}'.format(reponame), 'exists'
        break

# Add a new repository webhook.
functions.add_github_webhook(reponame, (github_temporary_token, 'x-oauth-basic'))

# Add a new repository deploy key.
deploy_key = functions.get_public_deploy_key(
    instance.dns_name, secret=github_temporary_token, salt='deploy-key')

functions.add_permanent_github_deploy_key(deploy_key, reponame, (username, password))

# Delete Github authorization.
functions.delete_temporary_github_authorization(github_auth_id, (username, password))

# Write domain name to Route 53.
cname = functions.create_cname_record(route53, reponame, instance.dns_name)

# Save details of instance.
functions.save_details(gdocs_credentials,
                       reponame, cname, instance, reponame, sheet_url, deploy_key)
