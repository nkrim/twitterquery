from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Count
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse, Http404
from django.shortcuts import get_object_or_404

from base64 import urlsafe_b64encode
from datetime import datetime
import json
import os
from time import sleep
from urllib.parse import quote_plus, urlencode, urlparse
from urllib.request import Request, urlopen
import zipfile
import zipstream

from .models import *
from .serializers import *

def makeJsonResponse(data, **kwargs):
	return JsonResponse(data, json_dumps_params={'separators':(',',':')}, **kwargs)

def makeJsonResponsePretty(data):
	output = json.dumps(data, indent=4)
	return HttpResponse(output, content_type='application/json')

'''
ERROR CODES
- 0: Missing query parameter
- 1: Empty query paramater
- 2: No authentication details
- 3: Error when querying twitter api
- 4: Rate limit exceeded (includes the 'wait' value)
- 5: Failed serach
- 6: Exception during status iteration
'''
def query(request):
	# HELPER FUNCTIONS FOR QUERY
	def get_bearer(auth):
		if auth.bearer != '':
			return auth.bearer
		cat = quote_plus(auth.key,'')+':'+quote_plus(auth.secret,'')
		bearer = urlsafe_b64encode(cat.encode()).decode()
		url = 'https://api.twitter.com/oauth2/token'
		data = urlencode([('grant_type','client_credentials')]).encode()
		headers = {
			'Authorization': 'Basic '+bearer,
			'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
		}
		try:
			response = urlopen(Request(url, data, headers, method='POST'))
			jsondict = json.loads(response.read().decode())
		except Exception as e:
			return auth.bearer
		else:
			if 'token_type' in jsondict and jsondict['token_type'] == 'bearer' and 'access_token' in jsondict and jsondict['access_token']:
				auth.bearer = jsondict['access_token']
				auth.save()
			return auth.bearer
	def get_search_results(bearer, q, max_id=None, min_id=None):
		params = [	('q',q),
					('result_type','recent'),
					('count',100)]
		if max_id:
			params.append(('max_id', max_id))
		if min_id:
			params.append(('since_id', min_id))
		query = urlencode(params)
		url = 'https://api.twitter.com/1.1/search/tweets.json?'+query
		headers = {
			'Authorization': 'Bearer '+bearer
		}
		try:
			response = urlopen(Request(url, headers=headers, method='GET'))
			results = json.loads(response.read().decode())
		except Exception as e:
			return (None, e)
		else:
			return (response, results)
	def perform_search(auth, q, max_id=None, min_id=None):
		response, results = get_search_results(auth.bearer, q, max_id, min_id)
		if response is None:
			return (False, JsonResponse({'success':False, 'code':3, 'error':'Error when querying twitter api: '+str(results)}, status=500))
		if response.status == 401:	# Repeat authentication steps by getting new bearer token
			auth.bearer = ''
			bearer = get_bearer(auth)
			response, results = get_search_results(bearer, search)
		if response is None:
			return (False, JsonResponse({'success':False, 'code':3, 'error':'Error when querying twitter api: '+str(results)}, status=500))
		if response.status == 429:
			return (False, JsonResponse({'success':False, 'code':4, 'error':'Rate limit exceeded', 'wait':response.getheader('X-Rate-Limit-Reset')-int(floot(time.time()))}, status=429))
		if response is None or response.status != 200 or len(results) == 0 or not 'search_metadata' in results or not 'statuses' in results:
			return (False, JsonResponse({'success':False, 'code':5, 'error':'Failed search: '+str(response.status_code)}, status=500))
		posts = results['statuses']
		if len(posts) == 0:
			return (True, {'posts': posts, 'empty':True})
		min_id = min([p['id'] for p in posts])
		# Filter posts
		posts = [p for p in posts if not 'retweeted_status' in p and 'extended_entities' in p and 'media' in p['entities']]
		for p in posts:
			p['media'] = [m for m in p['extended_entities']['media'] if 'type' in m and m['type'] == 'photo' and 'media_url' in m]
		posts = [p for p in posts if len(p['media']) > 0]
		return (True, {'posts': posts, 'max_id': results['search_metadata']['max_id'], 'min_id': min_id})
	def construct_statuses(search, posts):
		try:
			for p in posts:
				u = p['user']
				user, user_created = TwitterUser.objects.update_or_create(	user_id=u['id'], 
																			defaults={
																				'screen_name': u['screen_name'],
																				'name': u['name'],
																				'location': u['location'],
																				'followers_count': u['followers_count'],
																				'profile_image_url': u['profile_image_url']
																			})
				status, status_created = Status.objects.get_or_create(	created_by=user, status_id=p['id'], 
																		defaults={
																			'created_at': datetime.strptime(p['created_at'],'%a %b %d %X %z %Y'),
																			'text': p['text']
																		})
				status.searches.add(search)
				status.save()
				if status_created:
					media = p['media']
					for m in media:
						if 'sizes' in m:
							sizes = m['sizes']
							size = sizes.get('large') or sizes.get('medium') or sizes.get('small') or sizes.get('thumb') or {'w': 0, 'h': 0}
						else:
							size = {'w': 0, 'h': 0}
						Photo.objects.get_or_create(photo_id=m['id'],
													defaults={ 
														'photo_url': m['media_url'], 
														'height': size['h'],
														'width': size['w'],
														'status': status,
													})
		except Exception as e:
			# Cleanup to make sure no useless search is kept if it fails during construction
			for s in search.statuses.all():
				if s.searches.count() == 1:
					if s.created_by.statuses.count() == 1:
						s.created_by.delete()
					s.delete()
			search.delete()
			return (False, JsonResponse({'success':False, 'code':6, 'error':'Exception during status iteration: '+str(e)}, status=500))
		# Check for overlap and then merge
		overlaps = Search.objects.filter(query=search.query, max_id__gte=search.min_id).exclude(pk=search.pk)
		for o in overlaps:
			search.instances.update(search=o)
			o.statuses.add(*search.statuses.prefetch_related('searches').exclude(search=o))
			o.max_id = max(o.max_id, search.max_id)
			o.min_id = min(o.min_id, search.min_id)
			search.delete()
			o.save()
			search = o
		return (True, search)
	# MAIN BODY FOR QUERY
	# Parse query params
	q = request.GET.get('q',None)
	if q == None:
		return JsonResponse({'success':False, 'code':0, 'error':'Missing query parameter'}, status=400)
	if q == '':
		return JsonResponse({'success':False, 'code':1, 'error':'Empty query parameter'}, status=400)
	q = q.lower()
	limit = request.GET.get('limit',None)

	# Get initial bearer authentication
	site = get_current_site(request)
	if not hasattr(site, 'auth'):
		return JsonResponse({'success':False, 'code':2, 'error':'No authentication details found'}, status=500)
	auth = site.auth
	bearer = get_bearer(auth)

	# Do initial search and construct search and queryinstance
	success, results = perform_search(auth, q)
	if not success:
		return results
	if 'empty' in results:
		return JsonResponse({'success':True, 'empty':True, 'data':{}})
	posts = results['posts']
	search, created = Search.objects.get_or_create(query=q, max_id=results['max_id'], defaults={'min_id': results['min_id']})
	instance = QueryInstance.objects.create(query=q, max_id=results['max_id'], search=search)
	if limit:
		try:
			limitInt = int(limit)
		except ValueError:
			pass
		else:
			if limitInt > 0:
				instance.limit = min(100,limitInt)
				instance.save()

	# Consruct statuses
	if created:
		success, results = construct_statuses(search, posts)
		if not success:
			return results
		search = results
	else:
		search.save()

	# Repeat and iterate until the limit is reached or no more posts can be found
	while search.statuses.count() < instance.limit:
		# Perform search
		success, results = perform_search(auth, instance.query, search.min_id-1)
		if not success:
			return results
		if 'empty' in results:
			break
		posts = results['posts']
		search.max_id = max(search.max_id, results['max_id'])
		search.min_id = min(search.min_id, results['min_id'])
		# Construct statuses
		success, results = construct_statuses(search, posts)
		if not success:
			return results
		search = results
		search.save()

	# Return queryinstance withcompleted search
	instance.refresh_from_db(fields=('search',))
	instance.success = True
	instance.save()
	return makeJsonResponse({
			'success': True,
			'data': {
				'id': instance.pk,
				'query': instance.query,
				'limit': instance.limit,
				'time_of': instance.time_of,
				'success': instance.success,
				'statuses': StatusSerializer(instance.statuses(), many=True).data,
			}
		})

def get(request, query_pk):
	instance = get_object_or_404(QueryInstance, pk=query_pk)

	# Save search object to update access time
	instance.search.save()

	return makeJsonResponse({
			'id': instance.pk,
			'query': instance.query,
			'limit': instance.limit,
			'time_of': instance.time_of,
			'success': instance.success,
			'statuses': StatusSerializer(instance.statuses(), many=True).data,
		})

def download(request, query_pk):
	# HELPER FUNCTIONS FOR DOWNLOAD
	def zip_and_stream_photos(photos):
		z = zipstream.ZipFile(mode='w')
		errors = ''
		for screen_name, status_id, url in photos:
			try:
				filename = '{}@{}.{}'.format(status_id, screen_name, url.rpartition('.')[2])
				response = urlopen(url)
			except Exception as e:
				errors += filename+'\n'
			else:
				z.writestr(filename,response.read())
		if errors != '': 
			z.writestr('errors.txt', errors)
		return z
	# Get search object
	instance = get_object_or_404(QueryInstance, pk=query_pk)

	# Zip and stream pictures
	z = zip_and_stream_photos(instance.statuses().values_list('created_by__screen_name','photo','photo__photo_url'))

	# Save search object to update access time
	instance.search.save()

	# Return response with zipstream
	response = StreamingHttpResponse(z, content_type='application/zip')
	response['Content-Disposition'] = 'attachment; filename={}.zip'.format(instance)
	return response

def raw(request):
	# HELPER FUNCTIONS FOR QUERY
	def get_bearer(auth):
		if auth.bearer != '':
			return auth.bearer
		cat = quote_plus(auth.key,'')+':'+quote_plus(auth.secret,'')
		bearer = urlsafe_b64encode(cat.encode()).decode()
		url = 'https://api.twitter.com/oauth2/token'
		data = urlencode([('grant_type','client_credentials')]).encode()
		headers = {
			'Authorization': 'Basic '+bearer,
			'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
		}
		try:
			response = urlopen(Request(url, data, headers, method='POST'))
			jsondict = json.loads(response.read().decode())
		except Exception as e:
			return auth.bearer
		else:
			if 'token_type' in jsondict and jsondict['token_type'] == 'bearer' and 'access_token' in jsondict and jsondict['access_token']:
				auth.bearer = jsondict['access_token']
				auth.save()
			return auth.bearer
	def get_search_results(bearer, q, max_id=None, min_id=None):
		params = [	('q',q),
					('result_type','recent'),
					('count',100)]
		if max_id:
			params.append(('max_id', max_id))
		if min_id:
			params.append(('since_id', min_id))
		query = urlencode(params)
		url = 'https://api.twitter.com/1.1/search/tweets.json?'+query
		headers = {
			'Authorization': 'Bearer '+bearer
		}
		try:
			response = urlopen(Request(url, headers=headers, method='GET'))
			results = json.loads(response.read().decode())
		except Exception as e:
			return (None, e)
		else:
			return (response, results)
	# MAIN BODY FOR QUERY
	# Parse query params
	q = request.GET.get('q',None)
	if q == None:
		return JsonResponse({'success':False, 'code':0, 'error':'Missing query parameter'}, status=400)
	if q == '':
		return JsonResponse({'success':False, 'code':1, 'error':'Empty query parameter'}, status=400)
	q = q.lower()

	# Get initial bearer authentication
	site = get_current_site(request)
	if not hasattr(site, 'auth'):
		return JsonResponse({'success':False, 'code':2, 'error':'No authentication details found'}, status=500)
	auth = site.auth
	bearer = get_bearer(auth)

	# Do initial search and construct search and queryinstance
	response, results = get_search_results(bearer, q)
	return makeJsonResponsePretty(results)