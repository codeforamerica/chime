include_recipe "python"
package "git"

git "/home/migurski/bizarro-cms" do
  repository node['repo']
  reference node['ref']
  user "migurski"
  group "migurski"
end

execute "pip install -r requirements.txt" do
  cwd "/home/migurski/bizarro-cms"
end

execute "honcho export ... /etc/init" do
  command "honcho export -u migurski -a bizarro-cms upstart /etc/init"
  cwd "/home/migurski/bizarro-cms"
end

execute "stop bizarro-cms" do
  returns [0, 1]
end

execute "start bizarro-cms"
