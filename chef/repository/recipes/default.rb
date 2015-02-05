include_recipe "account"
package "git"

name = node[:user]
starter_repo = node[:starter]
github_repo = ENV['GITHUB_REPO']
github_token = ENV['GITHUB_TOKEN']

python "create Github repository" do
  user name
  code <<-GITHUB
import json, requests

info = dict(
    name='#{github_repo}',
    private=False, has_issues=False, has_wiki=False, has_downloads=False
    )

url = 'https://api.github.com/orgs/ceviche/repos'
head = {'Content-Type': 'application/json'}
auth = ('#{github_token}', 'x-oauth-basic')
resp = requests.post(url, json.dumps(info), headers=head, auth=auth)
code = resp.status_code

if code == 422:
    pass # Github repository already exists
elif code not in range(200, 299):
    raise RuntimeError('Github repository creation failed, status {}'.format(code))

with open('/home/#{name}/.ssh/id_rsa.pub') as file:
    input = dict(title='test-key', key=file.read())

url = 'https://api.github.com/repos/ceviche/#{github_repo}/keys'
resp = requests.post(url, json.dumps(input), headers=head, auth=auth)
code = resp.status_code

if code == 422:
    pass # Github deploy key already exists
elif code not in range(200, 299):
    raise RuntimeError('Github deploy key creation failed, status {}'.format(code))

GITHUB
end

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

bash "clone from starter repo to Github origin remote" do
  user name
  flags '-e'
  cwd '/var/opt/bizarro-site'
  code <<-GIT
git fetch #{starter_repo}
git branch master FETCH_HEAD

git remote add origin git@github.com:ceviche/#{github_repo}.git
git push -u origin master
GIT
end
