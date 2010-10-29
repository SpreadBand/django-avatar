from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('avatar.views',
    url('^add/$', 'add', name='avatar_add'),
    url('^change/$', 'change', name='avatar_change'),
    url('^delete/$', 'delete', name='avatar_delete'),
    url('^change_crop_delete$', 'change_crop_delete', name='avatar_change_crop_delete'),
    url('^crop/(?P<avatar_id>[\d]+)/$', 'crop', name='avatar_crop'),
    url('^render_primary/(?P<user>[\+\w]+)/(?P<size>[\d]+)/$', 'render_primary', name='avatar_render_primary'),    
)
