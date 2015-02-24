package 'git'
package 'python-pip'
execute 'pip install requests==2.2.1'

include_recipe "account"

name = node[:user]
starter_repo = node[:starter_repo]
github_org = node[:github_org]
github_repo = ENV['GITHUB_REPO']
github_temporary_token = ENV['GITHUB_TEMPORARY_TOKEN']

bash "init bare /var/opt/bizarro-site" do
  user 'root'
  flags '-e'
  code <<-GIT
DIR=`mktemp -d /tmp/bizarro-site-XXXXXX`
git init --shared=group --bare $DIR

chown -R #{name}:#{name} $DIR
chmod -R ug+rwX $DIR
chmod -R o+rX $DIR

rm -rf /var/opt/bizarro-site
mv $DIR /var/opt/bizarro-site
GIT
end

bash "clone from starter repo" do
  user name
  flags '-e'
  cwd '/var/opt/bizarro-site'
  code <<-GIT
git fetch #{starter_repo}
git branch master FETCH_HEAD
GIT
end

if github_repo and github_temporary_token then

python "create Github repository" do
  user name
  code <<-GITHUB
import json, requests

info = dict(
    name='#{github_repo}',
    private=False, has_issues=False, has_wiki=False, has_downloads=False
    )

url = 'https://api.github.com/orgs/#{github_org}/repos'
head = {'Content-Type': 'application/json'}
auth = ('#{github_temporary_token}', 'x-oauth-basic')
resp = requests.post(url, json.dumps(info), headers=head, auth=auth)
code = resp.status_code

if code == 422:
    pass # Github repository already exists
elif code not in range(200, 299):
    raise RuntimeError('Github repository creation failed, status {}'.format(code))

GITHUB
end

python "create Github deploy key" do
  user name
  code <<-GITHUB
import json, requests

with open('/home/#{name}/.ssh/id_rsa.pub') as file:
    input = dict(title='token-key', key=file.read())

url = 'https://api.github.com/repos/#{github_org}/#{github_repo}/keys'
head = {'Content-Type': 'application/json'}
auth = ('#{github_temporary_token}', 'x-oauth-basic')
resp = requests.post(url, json.dumps(input), headers=head, auth=auth)
code = resp.status_code

if code == 422:
    pass # Github deploy key already exists
elif code not in range(200, 299):
    raise RuntimeError('Github deploy key creation failed, status {}'.format(code))

GITHUB
end

bash "push to Github origin remote" do
  user name
  flags '-e'
  cwd '/var/opt/bizarro-site'
  code <<-GIT
git remote add origin git@github.com:#{github_org}/#{github_repo}.git
git push -u origin master
GIT
end

end
