require 'minitest/autorun'
require 'jekyll'
require 'directory-structure-generator'

class DSGTest < Minitest::Test

  class MockPage
    attr_reader :data, :path

    def initialize(layout, title)
      @data = {"layout" => layout, "title" => title}
      @path = "base/" + title.downcase + "/index.markdown"
    end
  end

  class MockSite
    attr_reader :pages

    def initialize(pages)
      @pages = pages
    end

    def add_page(page)
      @pages.push(page)
    end
  end

  def test_alphabetize_by_title
    # make a fake site object with some fake pages
    fake_site = MockSite.new([])
    layout = "category"
    titles = ["Anthicidae", "Scydmaenidae", "Paussinae", "Bostrychidae", "Scolytidae", "Anobiidae", "Meloidae", "Dermestidae", "Silphidae"]
    for title in titles
      fake_site.add_page(MockPage.new(layout, title))
    end

    # send it to generate() which modifies the fake_site object in place
    Jekyll::DirectoryStructureGenerator.new.generate(fake_site)

    # check a column array and verify that it's sorted alphabetically
    check_pages = fake_site.pages[0].data['columns'][0]['pages']
    title_list = []
    check_pages.each { |page| title_list.push(page['title'])}
    sorted_title_list = title_list.sort

    assert_equal sorted_title_list,
      title_list
  end

  def test_recognize_category_layout
    assert_equal true,
      Jekyll::DirectoryStructureGenerator.new.is_chime_page_layout("category")
  end

  def test_recognize_article_layout
    assert_equal true,
      Jekyll::DirectoryStructureGenerator.new.is_chime_page_layout("article")
  end

  def test_dont_recognize_nonsense_layout
    assert_equal false,
      Jekyll::DirectoryStructureGenerator.new.is_chime_page_layout("9283jfoewij")
  end

  def test_split_path
    assert_equal ["hello", "there", "world"],
      Jekyll::DirectoryStructureGenerator.new.make_path_split("hello/there/world")
  end

  def test_split_path_with_index
    assert_equal ["hello", "there", "world"],
      Jekyll::DirectoryStructureGenerator.new.make_path_split("hello/there/world/index.markdown")
  end
end
