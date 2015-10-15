# -- coding: utf-8 --
# Pattern used in calculating directory names for UserTask.
# This must be different from get_repo()'s, because they treat master differently.
USERTASK_DIRECTORY_PATTERN = 'usertask-{sha}-{email}'

# Pattern used in calculating directory names for old-style view_functions.get_repo().
# This must be different from UserTask's, because they treat master differently.
GETREPO_DIRECTORY_PATTERN = 'repo-{sha}-{email}'

# the different review states for an activity
# no changes have yet been made to the activity
REVIEW_STATE_FRESH = u'fresh'
# there are un-reviewed edits in the activity (or no edits at all)
REVIEW_STATE_EDITED = u'unreviewed edits'
# there are un-reviewed edits in the activity and a review has been requested
REVIEW_STATE_FEEDBACK = u'feedback requested'
# a review has happened and the site is ready to be published
REVIEW_STATE_ENDORSED = u'edits endorsed'
# the site has been published
REVIEW_STATE_PUBLISHED = u'changes published'

# the different working states for an activity
# the activity is not an activity yet, it's a representation of the live site
WORKING_STATE_LIVE = u'live'
# the activity is current and active
WORKING_STATE_ACTIVE = u'active'
# the activity has been published
WORKING_STATE_PUBLISHED = u'published'
# the activity has been deleted
WORKING_STATE_DELETED = u'deleted'

# different classifications for commits that modify an activity
# the commit represents the creation of an activity
ACTIVITY_COMMIT_CREATED = u'created'
# the commit represents the updating of an activity
ACTIVITY_COMMIT_UPDATED = u'updated'
# the commit represents the deletion of an activity
ACTIVITY_COMMIT_DELETED = u'deleted'
# the commit represents a merging into an activity
ACTICITY_COMMIT_MERGED = u'merged'

# the different categories and types of messages that can be displayed in the activity overview
# info messages, like starting an activity or changing its review or working state
COMMIT_CATEGORY_INFO = u'info'
COMMIT_TYPE_ACTIVITY_UPDATE = u'activity update'
COMMIT_TYPE_REVIEW_UPDATE = u'review update'
# edit messages, like creating or editing topics and articles
COMMIT_CATEGORY_EDIT = u'edit'
COMMIT_TYPE_EDIT = u'edit'
# comment messages, for leaving comments
COMMIT_CATEGORY_COMMENT = u'comment'
COMMIT_TYPE_COMMENT = u'comment'

# ISO language codes
ISO_CODE_ENGLISH = 'en'
ISO_NAME_ENGLISH = 'English'

# the name of the directory where Jekyll builds its site
JEKYLL_BUILD_DIRECTORY_NAME = '_site'

# when creating a content file, what extension should it have?
CONTENT_FILE_EXTENSION = u'markdown'

# the names of layouts, used in jekyll front matter and also in interface text
CATEGORY_LAYOUT = 'category'
ARTICLE_LAYOUT = 'article'
FOLDER_FILE_TYPE = 'folder'
FILE_FILE_TYPE = 'file'
IMAGE_FILE_TYPE = 'image'
# how we describe items based on their layout
LAYOUT_DISPLAY_LOOKUP = {
    CATEGORY_LAYOUT: 'topic',
    ARTICLE_LAYOUT: 'article',
    FOLDER_FILE_TYPE: 'folder',
    FILE_FILE_TYPE: 'file',
    IMAGE_FILE_TYPE: 'image'
}
LAYOUT_PLURAL_LOOKUP = {
    CATEGORY_LAYOUT: 'topics',
    ARTICLE_LAYOUT: 'articles',
    FOLDER_FILE_TYPE: 'folders',
    FILE_FILE_TYPE: 'files',
    IMAGE_FILE_TYPE: 'images'
}

# routes
ROUTE_ACTIVITY = '/activity'
ROUTE_BROWSE_LIVE = '/browse/'

# interface text
TEXT_ADD_CHANGE = u'Add a change to this activity'
