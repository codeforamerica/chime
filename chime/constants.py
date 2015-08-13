
class ChimeConstants:
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
    # the activity is current and active
    WORKING_STATE_ACTIVE = u'active'
    # the activity has been published
    WORKING_STATE_PUBLISHED = u'published'
    # the activity has been deleted
    WORKING_STATE_DELETED = u'deleted'

    @staticmethod
    def init_app(app):
        pass
