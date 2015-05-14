username = node[:user]

package 'rbenv'
package 'git'



repo_dir = File.realpath(File.join(File.dirname(__FILE__), '..', '..', '..'))

execute "jekyll/install-jekyll.sh" do
  cwd repo_dir
  user 'ubuntu'
end
