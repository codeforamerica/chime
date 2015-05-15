''' Setup script for new Chime instance in EC2.

Asks for Github login credentials and desired repository
name to create under https://github.com/chimecms organization.

Requires four environment variables:
- GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET for Github authorization.
- AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for Amazon EC2 setup.

Follows the process described here:
  https://github.com/chimecms/chime/issues/39#issuecomment-72957188

'''
from os import environ
from time import sleep
from chime.setup import functions as F

# Establish some baseline details.
gh_client_id, gh_client_secret, gdocs_client_id, gdocs_client_secret, \
    gh_username, gh_password, reponame, ec2, route53 = F.get_input(environ)

# Create a new authorization with Github.
gh_auth_id, gh_temporary_token = F.get_github_authorization(
    gh_client_id, gh_client_secret, (gh_username, gh_password))

# Ask for Google Docs credentials and create an authentication spreadsheet.
gdocs_credentials = F.authenticate_google(gdocs_client_id, gdocs_client_secret)
sheet_url = F.create_google_spreadsheet(gdocs_credentials, reponame)

# Verify status of Github authorization.
F.verify_github_authorization(gh_client_id, gh_client_secret,
                              gh_temporary_token, gh_auth_id)

# Set up EC2 instance.
if F.check_repo_state(reponame, gh_temporary_token):
    raise RuntimeError('Repository {} already exists, not going to run EC2'.format(reponame))

instance = F.create_ec2_instance(ec2, reponame, sheet_url, gdocs_client_id,
                                 gdocs_client_secret, gh_temporary_token)

while True:
    print '    Waiting for', reponame
    sleep(30)

    if F.check_repo_state(reponame, gh_temporary_token):
        print '-->', 'https://github.com/chimecms/{}'.format(reponame), 'exists'
        break

# Add a new repository webhook.
F.add_github_webhook(reponame, (gh_temporary_token, 'x-oauth-basic'))

# Add a new repository deploy key.
deploy_key = F.get_public_deploy_key(
    instance.dns_name, secret=gh_temporary_token, salt='deploy-key')

F.add_permanent_github_deploy_key(deploy_key, reponame, (gh_username, gh_password))

# Delete Github authorization.
F.delete_temporary_github_authorization(gh_auth_id, (gh_username, gh_password))

# Write domain name to Route 53.
cname = F.create_cname_record(route53, reponame, instance.dns_name)

# Save details of instance.
F.save_details(gdocs_credentials, reponame, cname, instance,
               reponame, sheet_url, deploy_key)
