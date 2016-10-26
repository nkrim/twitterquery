from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Count
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse, Http404
from django.shortcuts import get_object_or_404

from base64 import urlsafe_b64encode
from datetime import datetime
import json
import os
import sys
from time import sleep
import traceback
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
		posts = [p for p in posts 	if 		not 'retweeted_status' in p 
									and 	'extended_entities' in p 
									and 	'media' in p['entities'] 
									and 	not ('protected' in p['user'] and p['user']['protected'])]
		for p in posts:
			p['media'] = [m for m in p['extended_entities']['media'] 	if 		'type' in m 
																		and 	m['type'] == 'photo' 
																		and 	'media_url' in m]
		posts = [p for p in posts if len(p['media']) > 0]
		return (True, {'posts': posts, 'max_id': results['search_metadata']['max_id'], 'min_id': min_id})
	def construct_statuses(search, posts):
		# Check for overlap and then link
		next_search = Search.objects.exclude(pk=search.pk).filter(query=search.query, max_id__gte=search.min_id, statuses__isnull=False).first()
		if next_search:
			next_search.save()
			search.min_id = next_search.max_id+1
			search.next_search = next_search
			search.save()
		try:
			for p in posts:
				if p['id'] < search.min_id:
					continue
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
				search.statuses.add(status)
				if status_created:
					media = p['media']
					for m in media:
						if 'sizes' in m:
							sizes = m['sizes']
							size = sizes.get('large') or sizes.get('medium') or sizes.get('small') or sizes.get('thumb') or {'w': 0, 'h': 0}
						else:
							size = {'w': 0, 'h': 0}
						photo, photo_created = Photo.objects.get_or_create(	photo_id=m['id'],
																			defaults={ 
																				'photo_url': m['media_url'], 
																				'height': size['h'],
																				'width': size['w'],
																			})
						status.photos.add(photo)
		except Exception as e:
			# Cleanup to make sure no useless search is kept if it fails during construction
			for s in search.statuses.all():
				if s.searches.count() == 1:
					if s.created_by.statuses.count() == 1:
						s.created_by.delete()
					s.delete()
			search.delete()
			return (False, JsonResponse({'success':False, 'code':6, 'error':'Exception during status iteration: '+str(e)+':\n'+str(traceback.format_tb(sys.exc_info()[2]))}, status=500))
		return (True, next_search or search)
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

	# Repeat and iterate until the limit is reached or no more posts can be found
	while instance.status_count() < instance.limit:
		# Perform search
		success, results = perform_search(auth, instance.query, search.min_id-1)
		if not success:
			return results
		if 'empty' in results:
			break
		posts = results['posts']
		search.min_id = min(search.min_id, results['min_id'])
		# Construct statuses
		success, results = construct_statuses(search, posts)
		if not success:
			return results
		search = results

	# Return queryinstance withcompleted search
	instance.success = True
	instance.save()
	return makeJsonResponse({'success':True, 'data': QueryInstanceSerializer(instance).data})

def get(request, query_pk):
	instance = get_object_or_404(QueryInstance, pk=query_pk)
	# Save search object to update access time
	instance.search.save()
	return makeJsonResponsePretty(QueryInstanceSerializer(instance).data)

def download(request, query_pk):
	# HELPER CLASSES/FUNCTIONS FOR DOWNLOAD
	class QueryZipFile(zipstream.ZipFile):
		def __init__(self, qinst, *args, **kwargs):
			if not isinstance(qinst, QueryInstance):
				raise TypeError('qinst expected a QueryInstance object, but received %s' % qinst)
			super().__init__(*args, **kwargs)
			self.status_ids = [s.status_id for s in qinst.statuses()]
			self.photos = list(qinst.photos())
			for p in self.photos:
				p.filename = '{}.{}'.format(p, p.photo_url.rpartition('.')[2])
			self.info = [	'query_id: {}'.format(qinst.pk),	'time of: {}'.format(qinst.time_of),				'query: {}'.format(qinst.query), 			
							'limit: {}'.format(qinst.limit),	'status count: {}'.format(len(self.status_ids)),	'photo count: {}'.format(len(self.photos))	]
			self.errors = []

		def __iter__(self):
			for photo in self.photos: 
				for data in self.__write_photo(photo):
					yield data
			self.writestr('info.txt', '\n'.join(self.info).encode())
			if self.errors:
				self.writestr('errors.txt', '\n'.join(self.errors).encode())
			for data in super().__iter__():
				yield data

		def __write_photo(self, photo):
			try:
				response = urlopen(photo.photo_url)
			except Exception as e:
				self.__add_photo_error(photo, e)
				return iter(())
			else:
				self.__add_photo_info(photo)
				return self._ZipFile__write(arcname=photo.filename, iterable=response)

		def __add_photo_error(self, photo, e=None):
			self.errors.append('{} - {}: {}'.format(photo, photo.photo_url, e or 'Unknown Error'))

		def __add_photo_info(self, photo):
			photo_statuses = list(photo.statuses.filter(status_id__in=self.status_ids))
			photo_info = ['{}: {} status{} from this query'.format(photo.filename, len(photo_statuses), 'es' if len(photo_statuses) != 1 else '')]
			photo_info += ['\t{} - {}'.format(s, s.status_url()) for s in photo_statuses]
			self.info += photo_info
	# Get search object
	instance = get_object_or_404(QueryInstance, pk=query_pk)

	# Save search object to update access time
	instance.search.save()

	# Zip and stream pictures
	z = QueryZipFile(instance, compression=zipfile.ZIP_DEFLATED)

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