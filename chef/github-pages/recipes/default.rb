package 'ruby1.9.3'
package 'zlib1g-dev'

gem_package 'github-pages' do
    gem_binary '/usr/bin/gem1.9.3'
    options "--no-rdoc --no-ri"
    action :install
end

# Jekyll wants a JS runtime
package 'nodejs'
