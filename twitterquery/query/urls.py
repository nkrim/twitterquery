from django.conf.urls import url, include

from . import views

urlpatterns = [
	url(r'^$', views.query, name="query"),
	url(r'^(?P<search_pk>\d+)/', include([
		url(r'^$', views.get, name="get"),
		url(r'^download/$', views.download, name="download"),
	])),
]