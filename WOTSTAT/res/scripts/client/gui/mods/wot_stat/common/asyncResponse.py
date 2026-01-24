import BigWorld


json_headers = {
  'Content-type': 'application/json',
  'Accept': 'application/json'
}

API_URL_PREFIX = 'https://wotstat.info'
SERVERS_BASE_URL = [
  'https://wotstat.info',
  'https://ru.wotstat.info',
  'https://wotstat-proxy.ru'
]

currentServerIndex = 0

def next_server_index():
  global currentServerIndex
  currentServerIndex = (currentServerIndex + 1) % len(SERVERS_BASE_URL)
  return currentServerIndex

def getApiUrl(url):
  if url.startswith(API_URL_PREFIX):
    return url.replace(API_URL_PREFIX, SERVERS_BASE_URL[currentServerIndex], 1)
  return url

def get_async_api(url, headers={}, callback=None, error_callback=None, attempt=2):
  def on_error(res):
    next_server_index()
    if attempt > 0: get_async_api(url, headers, callback, error_callback, attempt - 1)
    elif error_callback: error_callback(res)

  get_async(getApiUrl(url), headers, callback, on_error)

def post_async_api(url, data=None, headers={}, callback=None, error_callback=None, attempt=0):
  def on_error(res):
    next_server_index()
    if attempt > 0: post_async_api(url, data, headers, callback, error_callback, attempt - 1)
    elif error_callback: error_callback(res)

  post_async(getApiUrl(url), data, headers, callback, on_error)

def get_async(url, headers={}, callback=None, error_callback=None):
  request_async(
    method='GET',
    url=url,
    headers=headers,
    postData=None,
    callback=callback,
    error_callback=error_callback
  )

def post_async(url, data=None, headers={}, callback=None, error_callback=None):
  request_async(
    method='POST',
    url=url,
    headers=headers,
    postData=data,
    callback=callback,
    error_callback=error_callback
  )

def request_async(method, url, headers, postData, callback, error_callback=None):

  def onComplete(result):
    # type: (str) -> None
    if result.responseCode != 200:
      if error_callback: error_callback(result)
      return
    else:
      if callback: callback(result.body)
      return

  BigWorld.fetchURL(url, onComplete, method=method, headers=headers, postData=postData, timeout=10)
