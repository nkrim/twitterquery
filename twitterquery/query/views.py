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

def raw(request):
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
	def get_search_results(bearer, search):
		query = urlencode([
			('q',search.query),
			('result_type','recent'),
			('count',str(search.limit))
		])
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
	# Parse query params
	q = request.GET.get('q',None)
	if q == None:
		return JsonResponse({'success':False, 'code':0, 'error':'Missing query parameter'}, status=400)
	if q == '':
		return JsonResponse({'success':False, 'code':1, 'error':'Empty query parameter'}, status=400)
	limit = request.GET.get('limit',None)
	retweets = request.GET.get('rt',None)

	# Construct the search object
	search = Search(query=q)
	if limit != None:
		try:
			search.limit = int(limit)
		except ValueError:
			pass
	if retweets != None and retweets.lower() == 'true':
		search.retweets = True


	# Get initial bearer authentication
	site = get_current_site(request)
	if not hasattr(site, 'auth'):
		return JsonResponse({'success':False, 'code':2, 'error':'No authentication details found'}, status=500)
	auth = site.auth
	bearer = get_bearer(auth)

	# Search for posts
	response, results = get_search_results(bearer, search)
	if response is None:
		return JsonResponse({'success':False, 'code':3, 'error':'Error when querying twitter api: '+str(results)}, status=500)
	if response.status == 401:	# Repeat authentication steps by getting new bearer token
		auth.bearer = ''
		bearer = get_bearer(auth)
		response, results = get_search_results(bearer, search)
	if response is None:
		return JsonResponse({'success':False, 'code':3, 'error':'Error when querying twitter api: '+str(results)}, status=500)
	if response.status == 429:
		return JsonResponse({'success':False, 'code':4, 'error':'Rate limit exceeded', 'wait':response.getheader('X-Rate-Limit-Reset')-int(floot(time.time()))}, status=429)
	if response is None or response.status != 200 or len(results) == 0 or not 'search_metadata' in results or not 'statuses' in results:
		return JsonResponse({'success':False, 'code':5, 'error':'Failed search: '+str(response.status_code)}, status=500)
	post_count = results['search_metadata']['count']
	posts = results['statuses']
	return makeJsonResponsePretty(posts)

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
	def get_search_results(bearer, search):
		query = urlencode([
			('q',search.query),
			('result_type','recent'),
			('count',str(search.limit))
		])
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
	# Parse query params
	q = request.GET.get('q',None)
	if q == None:
		return JsonResponse({'success':False, 'code':0, 'error':'Missing query parameter'}, status=400)
	if q == '':
		return JsonResponse({'success':False, 'code':1, 'error':'Empty query parameter'}, status=400)
	limit = request.GET.get('limit',None)
	retweets = request.GET.get('rt',None)

	# Construct the search object
	search = Search(query=q)
	if limit != None:
		try:
			search.limit = int(limit)
		except ValueError:
			pass
	if retweets != None and retweets.lower() == 'true':
		search.retweets = True


	# Get initial bearer authentication
	site = get_current_site(request)
	if not hasattr(site, 'auth'):
		return JsonResponse({'success':False, 'code':2, 'error':'No authentication details found'}, status=500)
	auth = site.auth
	bearer = get_bearer(auth)

	# Search for posts
	response, results = get_search_results(bearer, search)
	if response is None:
		return JsonResponse({'success':False, 'code':3, 'error':'Error when querying twitter api: '+str(results)}, status=500)
	if response.status == 401:	# Repeat authentication steps by getting new bearer token
		auth.bearer = ''
		bearer = get_bearer(auth)
		response, results = get_search_results(bearer, search)
	if response is None:
		return JsonResponse({'success':False, 'code':3, 'error':'Error when querying twitter api: '+str(results)}, status=500)
	if response.status == 429:
		return JsonResponse({'success':False, 'code':4, 'error':'Rate limit exceeded', 'wait':response.getheader('X-Rate-Limit-Reset')-int(floot(time.time()))}, status=429)
	if response is None or response.status != 200 or len(results) == 0 or not 'search_metadata' in results or not 'statuses' in results:
		return JsonResponse({'success':False, 'code':5, 'error':'Failed search: '+str(response.status_code)}, status=500)
	post_count = results['search_metadata']['count']
	posts = results['statuses']
	search.save() # Since search was succesful, save the search

	# Filter and contruct status objects
	try:
		for p in posts:
			if ('retweeted_status' in p ) and 'entities' in p and 'media' in p['entities']:
				media = [m for m in p['entities']['media'] if 'type' in m and m['type'] == 'photo' and 'media_url' in m and m['media_url']]
				if len(media) > 0:
					u = p['user']
					user, user_created = TwitterUser.objects.update_or_create(	user_id=u['id_str'], 
																				defaults={
																					'screen_name': u['screen_name'],
																					'name': u['name'],
																					'location': u['location'],
																					'followers_count': u['followers_count'],
																					'profile_image_url': u['profile_image_url']
																				})
					status, status_created = Status.objects.get_or_create(created_by=user, status_id=p['id_str'], 
																			defaults={
																				'created_at': datetime.strptime(p['created_at'],'%a %b %d %X %z %Y'),
																				'text': p['text']
																			})
					status.searches.add(search)
					status.save()
					if status_created:
						for m in media:
							if 'sizes' in m:
								sizes = m['sizes']
								size = sizes.get('large') or sizes.get('medium') or sizes.get('small') or sizes.get('thumb') or {'w': 0, 'h': 0}
							else:
								size = {'w': 0, 'h': 0}
							Photo.objects.get_or_create(photo_id=m['id_str'],
														defaults={ 
															'photo_url': m['media_url'], 
															'expanded_url': m['expanded_url'],
															'status': status,
															'height': size['h'],
															'width': size['w'],
														})
	except Exception as e:
		# Cleanup to make sure no useless search is kept if it fails during construction
		for s in search.statuses.all():
			if s.searches.count() == 1:
				if s.created_by.statuses.count() == 1:
					s.created_by.delete()
				s.delete()
		search.delete()
		return JsonResponse({'success':False, 'code':6, 'error':'Exception during status iteartion: '+str(e)}, status=500)

	# Construct and return JSON response from search object, if succesful
	else:
		serializer = SearchSerializer(search)
		return makeJsonResponse({'success':True, 'data':serializer.data})

def get(request, search_pk):
	search = get_object_or_404(Search, pk=search_pk)
	return makeJsonResponsePretty(SearchSerializer(search).data)

def download(request, search_pk):
	# HELPER FUNCTIONS FOR DOWNLOAD
	def zip_and_stream_photos(photos):
		z = zipstream.ZipFile(mode='w')
		errors = ''
		for screen_name, status_id, url in photos:
			try:
				filename = '{} {}.{}'.format(screen_name, status_id, url.rpartition('.')[2])
				response = urlopen(url)
			except Exception as e:
				errors += filename+'\n'
			else:
				z.writestr(filename,response.read())
		if errors != '': 
			z.writestr('errors.txt', errors)
		return z
	# Get search object
	search = get_object_or_404(Search, pk=search_pk)

	# Zip and stream pictures
	z = zip_and_stream_photos(search.statuses.values_list('created_by__screen_name','photo','photo__photo_url'))

	# Return response with zipstream
	response = StreamingHttpResponse(z, content_type='application/zip')
	response['Content-Disposition'] = 'attachment; filename={}.zip'.format(search)
	return response